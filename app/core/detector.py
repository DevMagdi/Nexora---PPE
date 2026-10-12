from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# مصادر الكشف: النماذج (`model:*`) أو طبقة الذكاء الجلدي (`skin:*`)
SOURCE_MODEL = "model"
SOURCE_SKIN_PREFIX = "skin:"


def is_skin_source(source: str | None) -> bool:
    """هل الكشف ده جه/اتأكّد من فلتر الجلد (distanceTransform / جسر العينين)؟"""
    return bool(source) and SOURCE_SKIN_PREFIX in source

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
    # Canonical (hybrid) names
    "Head Cap": (0, 255, 255),
    "NO-Head Cap": (0, 0, 255),
    "Lab Coat": (255, 0, 255),
    "Full Cover": (255, 255, 255),
    "Shoe Cover": (100, 200, 255),
}

# ألوان الكشوف المولّدة من فلتر الجلد/الجسر (هجين)
CLASS_COLORS_BY_NAME.setdefault("NO-Goggles", (80, 200, 255))
CLASS_COLORS_BY_NAME.setdefault("NO-Mask", (60, 60, 255))
CLASS_COLORS_BY_NAME.setdefault("NO-Gloves", (255, 120, 40))


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
    # مصدر الكشف: "model" أو "skin:eye_bridge" / "skin:mouth" / "skin:distance_transform"
    source: str = "model"


# ---------------------------------------------------------------------------
# Safe weight migration
# ---------------------------------------------------------------------------
# أوزان قديمة تم رفدها: ممنوع تحميلها تاني تحت أي ظرف (إعداد قديم في .env،
# fallback منسّي، أو صورة Docker قديمة). أي مسار بيطابقها بيتحوّل تلقائيًا
# للبديل المعتمد، فإعدادات المستخدمين القديمة تكمل شغل من غير تدخل يدوي.
RETIRED_MODEL_PATHS: tuple[str, ...] = (
    "Model/bestMedicalModel2.pt",
)

# خريطة الترحيل: وزن مرفود -> البديل المعتمد
MODEL_MIGRATIONS: dict[str, str] = {
    "Model/bestMedicalModel2.pt": "Model/bestMedicalModel.pt",
}


def _normalize_model_path(path: str | None) -> str:
    """مفتاح مقارنة موحّد لمسار الموديل (بدون اختلافات \\ أو ./ أو //)."""
    return os.path.normpath((path or "").strip().replace("\\", "/"))


def is_retired_model_path(path: str | None) -> bool:
    """
    هل المسار ده وزن مرفود؟

    المطابقة بالاسم الأساسي (basename) كمان، لأن الوزن نفسه هو المرفود —
    مش مكانه على الـ Disk — فأي نسخة منه في أي فولدر مرفوضة.
    """
    if not path:
        return False
    normalized = _normalize_model_path(path)
    retired_normalized = {_normalize_model_path(p) for p in RETIRED_MODEL_PATHS}
    retired_basenames = {
        os.path.basename(_normalize_model_path(p)) for p in RETIRED_MODEL_PATHS
    }
    return normalized in retired_normalized or os.path.basename(normalized) in retired_basenames


def migrate_model_path(path: str) -> str:
    """يرحّل أي وزن مرفود لبديله المعتمد (مع تحذير في اللوج)، وغير كده يرجع المسار زي ما هو."""
    if not is_retired_model_path(path):
        return path
    for retired, replacement in MODEL_MIGRATIONS.items():
        if _normalize_model_path(retired) == _normalize_model_path(path) or os.path.basename(
            _normalize_model_path(retired)
        ) == os.path.basename(_normalize_model_path(path)):
            logger.warning(
                "Model weight '%s' is retired; migrating to '%s'",
                path,
                replacement,
            )
            return replacement
    return path


def resolve_model_path(model_path: str, fallbacks: tuple[str, ...] = ()) -> str:
    """
    يحسم مسار الموديل على الـ Disk مع ترحيل آمن للأوزان المرفودة.

    * مسار مضبوط على وزن مرفود → يتحوّل للبديل المعتمد.
    * fallback مرفود → بيتخطّى دايمًا (ولو الملف موجود فعلًا).
    """
    migrated = migrate_model_path(model_path)
    if os.path.exists(migrated):
        return migrated
    for candidate in fallbacks:
        migrated_candidate = migrate_model_path(candidate)
        if is_retired_model_path(migrated_candidate):
            logger.warning("Skipping retired model weight in fallbacks: %s", candidate)
            continue
        if os.path.exists(migrated_candidate):
            logger.warning(
                "Configured model '%s' not found; falling back to '%s'",
                model_path,
                migrated_candidate,
            )
            return migrated_candidate
    return migrated


def sanitize_class_conf_thresholds(
    class_names: dict[int, str], thresholds: dict[int, float]
) -> dict[int, float]:
    """
    ينظّف خريطة عتبات الثقة لكل فئة بعد ترحيل الأوزان.

    أرقام الفئات (class ids) في ``.env`` القديم ممكن تشير لفئات مش موجودة في
    الوزن الجديد — الإبقاء عليها بيغلط العتبات على فئات تانية خالص، فبنرمي
    أي id مش معروف للموديل المحمّل ونسجّله في اللوج.
    """
    if not thresholds:
        return {}
    valid_ids = set(class_names)
    kept = {cid: thr for cid, thr in thresholds.items() if cid in valid_ids}
    dropped = sorted(set(thresholds) - set(kept))
    if dropped:
        logger.warning(
            "Dropped class-conf thresholds for unknown class ids %s (model classes: %s)",
            dropped,
            sorted(valid_ids),
        )
    return kept


class PPEDetector:
    def __init__(
        self,
        model_path: str,
        confidence: float,
        default_class_conf: float,
        class_conf_thresholds: str = "",
        fallbacks: tuple[str, ...] = (),
    ) -> None:
        from ultralytics import YOLO

        resolved_path = resolve_model_path(model_path, fallbacks)
        self.model = YOLO(resolved_path)
        self.confidence = confidence
        self.default_class_conf = default_class_conf
        # بعد ترحيل الأوزان: أي عتبة لفئة مش موجودة في الموديل الجديد بتتشال
        self.class_conf = sanitize_class_conf_thresholds(
            self.model.names, settings.parse_class_thresholds_str(class_conf_thresholds)
        )
        self._lock = threading.Lock()

        logger.info("PPEDetector loaded: %s (global_conf=%.2f)", resolved_path, confidence)
        logger.info("Default class conf: %.2f", self.default_class_conf)
        logger.info("Class-specific conf map: %s", self.class_conf)
        logger.info("Model classes: %s", self.model.names)

    @property
    def class_names(self) -> dict[int, str]:
        return self.model.names

    def detect(self, frame: np.ndarray) -> list[Detection]:
        # YOLO predictor instance is not thread-safe across concurrent run_in_executor calls
        with self._lock:
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
