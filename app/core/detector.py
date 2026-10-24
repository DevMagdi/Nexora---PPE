from __future__ import annotations

import hashlib
import math
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.core.model_policy import MODEL_FILENAME, validate_model_path
from app.core.ppe import canonical_class_name, is_negative_class

logger = get_logger(__name__)
# OpenCV uses BGR. Gold equipment, neutral people, red violations.
GOLD_BGR = (39, 162, 201)
TEXT_BGR = (232, 232, 232)
DANGER_BGR = (85, 85, 229)


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    color: tuple[int, int, int] = GOLD_BGR
    source: str = "model"


def require_model_file(model_path: str | None = None) -> Path:
    path = validate_model_path(model_path or settings.PPE_MODEL_PATH)
    if not path.is_file():
        raise FileNotFoundError(
            f"Required industrial weights are missing: {path}. Install the approved "
            f"{MODEL_FILENAME} artifact, then run `python -m app.model_check`. "
            "Inference is disabled; no fallback or automatic download is permitted."
        )
    if path.stat().st_size == 0:
        raise RuntimeError(
            f"The approved weights at {path} are empty; re-copy the complete artifact"
        )
    return path


def weight_fingerprint(path: str | Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return {
        "filename": MODEL_FILENAME,
        "size_bytes": Path(path).stat().st_size,
        "sha256": digest.hexdigest(),
    }


def validate_class_names(names: dict[int, str] | list[str]) -> dict[int, str]:
    items = names.items() if isinstance(names, dict) else enumerate(names)
    canonical: dict[int, str] = {}
    for class_id, name in items:
        normalized = canonical_class_name(name)
        if not normalized:
            raise RuntimeError("Checkpoint contains a class outside the industrial PPE allowlist")
        if normalized in canonical.values():
            raise RuntimeError("Checkpoint contains ambiguous duplicate industrial classes")
        canonical[int(class_id)] = normalized
    required = {"Person", "Hardhat", "NO-Hardhat", "Safety Vest", "NO-Safety Vest"}
    if not required.issubset(canonical.values()):
        raise RuntimeError(
            "Checkpoint must include Person, Hardhat and Safety Vest with their violation classes"
        )
    return canonical


class PPEDetector:
    """One shared, thread-safe detector for RTSP, images, video and camera workers."""

    def __init__(self) -> None:
        path = require_model_file()
        self.weights_fingerprint = weight_fingerprint(path)
        expected = settings.PPE_MODEL_SHA256.lower()
        if expected and self.weights_fingerprint["sha256"] != expected:
            raise RuntimeError(
                "Approved checkpoint SHA-256 verification failed; inference will not start"
            )
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Install inference dependencies with `pip install -r requirements.txt`"
            ) from exc
        try:
            # The on-disk check above prevents ultralytics from downloading a different checkpoint.
            self.model = YOLO(str(path), task="detect")
        except Exception as exc:
            raise RuntimeError(
                f"Cannot load {MODEL_FILENAME}; verify that the artifact is complete and compatible"
            ) from exc
        if getattr(self.model, "task", None) != "detect":
            raise RuntimeError("The approved checkpoint must be an object detection model")
        self.class_names = validate_class_names(self.model.names)
        self.confidence = settings.DETECTION_CONFIDENCE
        self._lock = threading.Lock()
        logger.info(
            "Industrial detector ready: %s conf=%.2f", self.weights_fingerprint, self.confidence
        )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if (
            not isinstance(frame, np.ndarray)
            or frame.ndim != 3
            or frame.shape[2] != 3
            or not frame.size
        ):
            raise ValueError("Expected a non-empty BGR image")
        height, width = frame.shape[:2]
        detections: list[Detection] = []
        with self._lock:
            results = self.model(frame, conf=self.confidence, verbose=False)
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    name = self.class_names.get(class_id)
                    conf = float(box.conf[0])
                    coords = [float(v) for v in box.xyxy[0]]
                    if not name or not math.isfinite(conf) or not self.confidence <= conf <= 1.0:
                        continue
                    if len(coords) != 4 or not all(math.isfinite(v) for v in coords):
                        continue
                    x1, y1, x2, y2 = coords
                    x1, x2 = max(0, min(width, int(x1))), max(0, min(width, int(x2)))
                    y1, y2 = max(0, min(height, int(y1))), max(0, min(height, int(y2)))
                    if x2 <= x1 or y2 <= y1:
                        continue
                    color = (
                        DANGER_BGR
                        if is_negative_class(name)
                        else TEXT_BGR
                        if name == "Person"
                        else GOLD_BGR
                    )
                    detections.append(Detection(class_id, name, conf, x1, y1, x2, y2, color))
        return detections
