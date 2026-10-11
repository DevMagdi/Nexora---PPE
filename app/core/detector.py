from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# ألوان (نغطي construction + medical names)
CLASS_COLORS_BY_NAME = {
    # Construction
    "Hardhat": (255, 0, 0),
    "NO-Hardhat": (0, 0, 255),
    "Safety Vest": (0, 255, 255),
    "NO-Safety Vest": (255, 0, 255),
    "Mask": (0, 255, 0),
    "NO-Mask": (255, 255, 0),
    "Person": (200, 200, 200),
    "Gloves": (255, 165, 0),
    "NO-Gloves": (255, 80, 0),
    "Safety Boots": (100, 200, 255),
    "NO-Safety Boots": (80, 120, 255),
    "Goggles": (180, 255, 180),
    "NO-Goggles": (120, 220, 120),

    # Medical (lowercase)
    "mask": (0, 255, 0),
    "no mask": (0, 0, 255),
    "hand gloves": (255, 165, 0),
    "no hand gloves": (0, 0, 255),
    "head cap": (0, 255, 255),
    "no head cap": (0, 0, 255),
    "goggle": (180, 255, 180),
    "no goggle": (120, 220, 120),
    "lab coat": (255, 0, 255),
    "full cover": (255, 255, 255),
    "shoe cover": (100, 200, 255),
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
    def __init__(
        self,
        model_path: str,
        confidence: float,
        default_class_conf: float,
        class_conf_thresholds: str = "",
    ) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.confidence = confidence

        self.default_class_conf = default_class_conf
        self.class_conf = settings.parse_class_thresholds_str(class_conf_thresholds)

        logger.info("PPEDetector loaded: %s (global_conf=%.2f)", model_path, confidence)
        logger.info("Default class conf: %.2f", self.default_class_conf)
        logger.info("Class-specific conf map: %s", self.class_conf)
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
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                thr = self.class_conf.get(cls_id, self.default_class_conf)
                if conf < thr:
                    continue

                name = self.model.names.get(cls_id, str(cls_id))
                color = CLASS_COLORS_BY_NAME.get(name, (200, 200, 200))

                detections.append(
                    Detection(
                        class_id=cls_id,
                        class_name=name,
                        confidence=conf,
                        x1=int(box.xyxy[0][0]),
                        y1=int(box.xyxy[0][1]),
                        x2=int(box.xyxy[0][2]),
                        y2=int(box.xyxy[0][3]),
                        color=color,
                    )
                )

        return detections