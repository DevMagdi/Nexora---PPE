from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ppe import canonical_class_name

logger = get_logger(__name__)

# أزواج الفئات الموجبة/السالبة لمنع انعكاس عتبات الثقة (موجب أعلى من سالب)
_POSITIVE_TO_NEGATIVE_CANONICAL: dict[str, str] = {
    "Hardhat": "NO-Hardhat",
    "Safety Vest": "NO-Safety Vest",
    "Mask": "NO-Mask",
    "Gloves": "NO-Gloves",
    "Safety Boots": "NO-Safety Boots",
    "Goggles": "NO-Goggles",
    "Head Cap": "NO-Head Cap",
}

# مصادر الكشف: النماذج (`model:*`) أو طبقة الذكاء الجلدي (`skin:*`)
SOURCE_MODEL = "model"
SOURCE_SKIN_PREFIX = "skin:"


def is_skin_source(source: str | None) -> bool:
    """
    هل الكشف ده **مولَّد** من فلتر الجلد (distanceTransform / جسر العينين / الفم)؟

    مهم نستخدم ``startswith`` مش مجرد بحث عن ``skin:`` — لأن الكشف الموديلي
    اللي اتأكّد بالجلد بياخد source مثل ``model:construction+skin:mouth``،
    وده فنيًا كشف موديل مؤكَّد وثقته كاملة في منطق المخالفات، مش كشف صناعي.
    """
    return bool(source) and source.startswith(SOURCE_SKIN_PREFIX)

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


def require_model_file(
    model_path: str,
    fallbacks: tuple[str, ...] = (),
    *,
    setting_name: str = "",
) -> str:
    """Resolve a model path and fail fast with an actionable error when no weights exist.

    Checks the configured path (after safe weight migration) plus every fallback,
    so a typo'd ``.env`` path or a missing ``Model/*.pt`` file surfaces as a clear
    ``FileNotFoundError`` instead of an obscure YOLO/ultralytics traceback.
    """
    resolved = resolve_model_path(model_path, fallbacks)
    if os.path.exists(resolved):
        return resolved
    candidates = ", ".join([model_path, *fallbacks]) or "(none)"
    where = f" (setting {setting_name})" if setting_name else ""
    raise FileNotFoundError(
        f"Detection model weights not found{where}. Checked: {candidates} "
        f"(resolved to {resolved!r}). Put the .pt weights in Model/ or fix the model "
        "path in .env (CONSTRUCTION_MODEL_PATH / MEDICAL_MODEL_PATH). "
        "See docs/LOCAL_RUN_TROUBLESHOOTING_AR.md."
    )


def sanitize_class_conf_thresholds(
    class_names: dict[int, str],
    thresholds: dict[int, float],
    *,
    migrated_from_retired: bool = False,
) -> dict[int, float]:
    """
    ينظّف خريطة عتبات الثقة لكل فئة بعد ترحيل الأوزان.

    * لو الموديل نفسه جاي من مسار مرفود (مثل ``bestMedicalModel2.pt``) وتم
      ترحيله تلقائيًا إلى ``bestMedicalModel.pt``، فترتيب وأرقام الفئات تغيّر
      بالكامل حتى لو الأرقام ما زالت داخل ``0..10`` — لذلك نُسقط الخريطة القديمة
      بالكامل حتى لا تُفرض عتبة 0.70 على الفئات الموجبة (`hand gloves` / `mask`).
    * في الحالات العادية، نرمي أي id غير موجود في الموديل المحمّل ونسجّله.
    """
    if not thresholds:
        return {}
    if migrated_from_retired:
        logger.warning(
            "Discarded stale class-conf thresholds %s from retired model weight "
            "(class IDs do not match replacement model classes %s)",
            thresholds,
            class_names,
        )
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


def sanitize_inverted_class_thresholds(
    class_names: dict[int, str],
    thresholds: dict[int, float],
    default_class_conf: float,
    *,
    model_label: str = "",
) -> dict[int, float]:
    """
    يمنع انعكاس عتبات الثقة بين الفئة الموجبة والفئة السالبة المقابلة لها.

    في بقايا إعدادات ``bestMedicalModel2.pt``، كانت الفئة ``2`` (`hand gloves`)
    والفئة ``5`` (`mask`) تأخذان ``0.70`` بينما الفئات السالبة ``7`` (`no hand gloves`)
    و ``9`` (`no mask`) تأخذ ``0.25–0.30``، مما يجعل النظام يعمى عن الكمامة/القفاز
    ويسجل مخالفة فورية. إذا كانت عتبة الفئة الموجبة أعلى من عتبة الفئة السالبة
    المقابلة لها، نخفّض عتبة الموجب لتطابق عتبة السالب (أو العتبة الافتراضية).
    """
    if not thresholds or not class_names:
        return dict(thresholds)

    canonical_to_id: dict[str, int] = {
        canonical_class_name(name): cid for cid, name in class_names.items()
    }
    adjusted = dict(thresholds)
    prefix = f"[{model_label}] " if model_label else ""

    for pos_canon, neg_canon in _POSITIVE_TO_NEGATIVE_CANONICAL.items():
        pos_id = canonical_to_id.get(pos_canon)
        neg_id = canonical_to_id.get(neg_canon)
        if pos_id is None or neg_id is None or pos_id not in adjusted:
            continue
        pos_thr = adjusted[pos_id]
        neg_thr = adjusted.get(neg_id, default_class_conf)
        if pos_thr > neg_thr:
            logger.warning(
                "%sClass conf threshold %.2f for positive class %d (%r) exceeds "
                "negative class %d (%r) threshold %.2f; clamping positive to %.2f",
                prefix,
                pos_thr,
                pos_id,
                class_names.get(pos_id, pos_canon),
                neg_id,
                class_names.get(neg_id, neg_canon),
                neg_thr,
                neg_thr,
            )
            adjusted[pos_id] = neg_thr

    return adjusted


def apply_confidence_floor(
    global_conf: float,
    class_conf: dict[int, float],
    floor: float,
    *,
    model_label: str = "",
) -> tuple[float, dict[int, float]]:
    """
    يرفع أي عتبة ثقة أقل من الأرضية الدنيا (``DETECTION_CONFIDENCE_FLOOR``).

    إعدادات منخفضة أوي (0.05 / 0.10) بتنتج كشوف وهمية بكتلة — زي اللي ظهر في
    لوج 2026-10-12: Person بيتقلب بين 0.26 و 0.93 كل فريم وكشوف صناعية بثقة
    0.96. الأرضية دي حاجز أدنى للدقة بلا مساس بإعدادات المستخدم الأعلى.

    يرجع ``(global_conf_after, class_conf_after)`` مع تحذير في اللوج لكل قيمة
    اترفعت.
    """
    if floor <= 0:
        return global_conf, class_conf

    if global_conf < floor:
        logger.warning(
            "%sGlobal detection confidence %.2f is below the precision floor %.2f; raising it",
            f"[{model_label}] " if model_label else "",
            global_conf,
            floor,
        )
        global_conf = floor

    raised: dict[int, float] = {}
    adjusted: dict[int, float] = {}
    for cid, thr in class_conf.items():
        if thr < floor:
            raised[cid] = floor
            adjusted[cid] = floor
        else:
            adjusted[cid] = thr
    if raised:
        logger.warning(
            "%sClass conf threshold(s) %s below the precision floor %.2f were raised",
            f"[{model_label}] " if model_label else "",
            raised,
            floor,
        )

    return global_conf, adjusted


class PPEDetector:
    def __init__(
        self,
        model_path: str,
        confidence: float,
        default_class_conf: float,
        class_conf_thresholds: str = "",
        fallbacks: tuple[str, ...] = (),
        *,
        setting_name: str = "",
    ) -> None:
        # Check weights on disk BEFORE importing ultralytics/torch, so a missing
        # .pt file surfaces as a clear FileNotFoundError even when the ML stack
        # is not installed yet.
        resolved_path = require_model_file(model_path, fallbacks, setting_name=setting_name)
        try:
            from ultralytics import YOLO
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The 'ultralytics' package is not installed, so YOLO models cannot load. "
                "Install backend dependencies with `pip install -r requirements.txt`."
            ) from exc

        self.model = YOLO(resolved_path)
        self.confidence = confidence
        self.default_class_conf = default_class_conf
        model_label = os.path.basename(resolved_path)
        # بعد ترحيل الأوزان: لو المسار الأصلي مرفود تتشال خريطة الـ class ids القديمة بالكامل،
        # وفي الحالات العادية تتشال أي فئة غير موجودة في الموديل
        self.class_conf = sanitize_class_conf_thresholds(
            self.model.names,
            settings.parse_class_thresholds_str(class_conf_thresholds),
            migrated_from_retired=is_retired_model_path(model_path),
        )
        # حاجز الدقة: عتبات أقل من الأرضية الدنيا بتترفع تلقائيًا (بلوج تحذيري)
        self.confidence, self.class_conf = apply_confidence_floor(
            self.confidence,
            self.class_conf,
            settings.DETECTION_CONFIDENCE_FLOOR,
            model_label=model_label,
        )
        # الـ default class conf نفسه مش فايت من الخريطة — نطبّق عليه الأرضية كمان
        if self.default_class_conf < settings.DETECTION_CONFIDENCE_FLOOR:
            logger.warning(
                "[%s] Default class conf %.2f is below the precision floor %.2f; raising it",
                model_label,
                self.default_class_conf,
                settings.DETECTION_CONFIDENCE_FLOOR,
            )
            self.default_class_conf = settings.DETECTION_CONFIDENCE_FLOOR
        # منع انعكاس العتبات (موجب أعلى من السالب المقابل له) حتى لو المسار اتعدّل يدويًا
        self.class_conf = sanitize_inverted_class_thresholds(
            self.model.names,
            self.class_conf,
            self.default_class_conf,
            model_label=model_label,
        )
        self._lock = threading.Lock()

        logger.info("PPEDetector loaded: %s (global_conf=%.2f)", resolved_path, self.confidence)
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
