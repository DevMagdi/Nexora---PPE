from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.core.model_policy import (
    MODEL_FILENAME,
    UNIFIED_REJECTION_MESSAGE,
    sha256_file,
    validate_model_path,
)
from app.core.postprocess import resolve_ppe_conflicts
from app.core.ppe import (
    DANGER_BGR as DANGER_BGR,
)
from app.core.ppe import (
    EXPECTED_MODEL_CLASSES,
    canonical_class_name,
    is_ignored_model_class,
    is_negative_class,
    supported_negative_rules,
)
from app.core.ppe import (
    GOLD_BGR as GOLD_BGR,
)
from app.core.ppe import (
    TEXT_BGR as TEXT_BGR,
)

logger = get_logger(__name__)


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
    person_index: int | None = None


def require_model_file(model_path: str | None = None) -> Path:
    """Resolve, validate and (when pinned) hash-check the single approved weight."""
    try:
        path = validate_model_path(model_path or settings.PPE_MODEL_PATH)
    except ValueError as exc:
        message = str(exc)
        if UNIFIED_REJECTION_MESSAGE in message:
            raise ValueError(UNIFIED_REJECTION_MESSAGE) from exc
        raise
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
    expected = settings.PPE_MODEL_SHA256.strip().lower()
    if expected and sha256_file(path) != expected:
        raise RuntimeError(
            "Approved checkpoint SHA-256 verification failed; inference will not start. "
            f"Expected {expected} for {MODEL_FILENAME}"
        )
    return path


def weight_fingerprint(path: str | Path) -> dict[str, object]:
    return {
        "filename": MODEL_FILENAME,
        "size_bytes": Path(path).stat().st_size,
        "sha256": sha256_file(path),
    }


def validate_class_names(names: dict[int, str] | list[str]) -> dict[int, str]:
    items = names.items() if isinstance(names, dict) else enumerate(names)
    canonical: dict[int, str] = {}
    skipped: list[str] = []
    ignored: list[str] = []
    for class_id, name in items:
        normalized = canonical_class_name(name)
        if not normalized:
            (ignored if is_ignored_model_class(name) else skipped).append(str(name))
            continue
        if normalized in canonical.values():
            continue
        canonical[int(class_id)] = normalized

    if ignored:
        logger.info("Ignoring non-industrial checkpoint classes (Mask/NO-Mask): %s", ignored)
    if skipped:
        logger.warning("Ignoring unknown classes in checkpoint: %s", skipped)

    # Minimum contract of the approved Model/ppe.pt checkpoint.
    required = {"Person", "Hardhat", "NO-Hardhat", "Safety Vest"}
    missing = required - set(canonical.values())
    if missing:
        raise RuntimeError(
            f"Checkpoint missing required classes: {sorted(missing)}. "
            f"Loaded: {sorted(set(canonical.values()))}"
        )

    loaded = set(canonical.values())
    absent_expected = [
        name
        for name in EXPECTED_MODEL_CLASSES
        if canonical_class_name(name) and canonical_class_name(name) not in loaded
    ]
    if absent_expected:
        logger.warning(
            "Approved checkpoint lacks expected classes (their rules stay display-only): %s",
            absent_expected,
        )

    logger.info("Industrial classes loaded: %s", sorted(loaded))
    return canonical


class PPEDetector:
    """One shared, thread-safe detector for RTSP, images, video and camera workers."""

    def __init__(self) -> None:
        # require_model_file enforces the ppe.pt name after resolve, rejects any
        # unified reference, checks the file and verifies the optional SHA-256 pin.
        path = require_model_file()
        self.weights_fingerprint = weight_fingerprint(path)
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

    @property
    def supported_negative_rules(self) -> frozenset[str]:
        return supported_negative_rules(self.class_names)

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
        return resolve_ppe_conflicts(detections, display_confidence=self.confidence)
