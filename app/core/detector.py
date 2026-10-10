from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)

CLASS_COLORS_BY_NAME = {
    "Hardhat": (255, 0, 0),
    "NO-Hardhat": (0, 0, 255),
    "Safety Vest": (0, 255, 255),
    "NO-Safety Vest": (255, 0, 255),
    "Mask": (0, 255, 0),
    "NO-Mask": (255, 255, 0),
    "Person": (200, 200, 200),

    # اختياري (لو تحب تلوّنهم)
    "Gloves": (255, 165, 0),
    "NO-Gloves": (255, 80, 0),
    "Safety Boots": (100, 200, 255),
    "NO-Safety Boots": (80, 120, 255),
    "Goggles": (180, 255, 180),
    "NO-Goggles": (120, 220, 120),
}

@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    color: tuple[int, int, int]

class PPEDetector:
    def __init__(self, model_path: str, confidence: float = 0.5) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.confidence = confidence
        logger.info("PPEDetector loaded: %s (conf=%.2f)", model_path, confidence)
        logger.info("Model classes: %s", self.model.names)

        logger.info("Model classes: %s", self.model.names)
    @property
    def class_names(self) -> dict[int, str]:
        return self.model.names

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self.model(frame, conf=self.confidence, verbose=False)
        detections: list[Detection] = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls = int(box.cls[0])
                name = self.model.names[cls]
                color = CLASS_COLORS_BY_NAME.get(name, (200, 200, 200))

                detections.append(
                    Detection(
                        class_id=cls,
                        class_name=name,
                        confidence=float(box.conf[0]),
                        x1=int(box.xyxy[0][0]),
                        y1=int(box.xyxy[0][1]),
                        x2=int(box.xyxy[0][2]),
                        y2=int(box.xyxy[0][3]),
                        color=color,
                    )
                )

        return detections