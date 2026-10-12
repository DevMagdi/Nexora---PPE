from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.detector import Detection, is_skin_source
from app.core.logging import get_logger
from app.core.ppe import (
    CONSTRUCTION_ONLY_CLASSES,
    PPE_CLASS_MAPS,
    Profile,
    canonical_class_name,
    sanitize_enabled_classes,
)

logger = get_logger(__name__)

PPE_PRIORITY: list[str] = [
    "helmet",
    "vest",
    "mask",
    "gloves",
    "goggles",
    "boots",
    "cap",
    "coat",
    "full_cover",
    "shoe_cover",
]
MIN_PERSON_OVERLAP = 0.4
# أدنى ثقة ليعتبر الـ Person من الموديل الإنشائي "سياقاً موثوقاً" في كاميرا طبية
# (كان أي Person بـ 0.26 يتقلب بيكتب مخالفات "ناقص بالطو/غطاء" على الفاضي)
MIN_MEDICAL_CONTEXT_CONF = 0.35


@dataclass
class ViolationEvent:
    camera_id: int
    violation_type: str
    confidence: float
    frame_path: str | None = None
    violation_id: int | None = None


@dataclass
class _PPEState:
    last_seen_time: float = field(default_factory=time.time)
    last_alert_time: float = 0.0
    last_negative_time: float = 0.0


def _norm_name(s: str) -> str:
    """
    مفتاح موحّد لأسماء الفئات.

    النظام الهجين بيخلط أسماء الموديل الطبي (`no goggle`) مع الأسماء الإنشائية
    (`NO-Goggles`) ومع الكشوف المولّدة من فلتر الجلد، فالمقارنة بقت على الصيغة
    الموحّدة بدل مجرد lowercase.
    """
    return canonical_class_name(s).lower()


@dataclass
class _CameraState:
    ppe_states: dict[str, _PPEState] = field(default_factory=dict)

    def state_for(self, ppe_key: str) -> _PPEState:
        if ppe_key not in self.ppe_states:
            self.ppe_states[ppe_key] = _PPEState()
        return self.ppe_states[ppe_key]


_MEDICAL_CONTEXT_NAMES: set[str] = {"person"} | {
    _norm_name(str(cfg[key]))
    for cfg in PPE_CLASS_MAPS["medical"].values()
    for key in ("positive", "negative")
    if cfg.get(key)
}


def _has_medical_context(detections: list[Detection]) -> bool:
    """
    فيه سياق طبي موثوق في الكادر؟

    الشخص ممكن يجي من الموديل الإنشائي (النظام الهجين)، والقطع الطبية من
    الموديل الطبي — الاتنين يعتبروا دليل على وجود طاقم في الكادر.

    الشخص الضعيف (تحت ``MIN_MEDICAL_CONTEXT_CONF``) مش بيعتبر سياقاً — كان
    بيخلي كاميرا طبية تكتب "ناقص بالطو/غطاء كامل" لمجرد بوكس متقلب من
    الموديل الإنشائي على خلفية، وده اللي حصل في اللوج.
    """
    return any(
        _norm_name(d.class_name) in _MEDICAL_CONTEXT_NAMES
        and (
            _norm_name(d.class_name) != "person"
            or d.confidence >= MIN_MEDICAL_CONTEXT_CONF
        )
        for d in detections
    )


def _violation_evidence_conf(
    detections: list[Detection],
    negative: str,
    *,
    min_skin_conf: float | None = None,
) -> float | None:
    """
    أعلى ثقة صالحة كـ **دليل مخالفة** لفئة سالبة على الكادر، أو ``None``.

    الكشوف المولَّدة من فلتر الجلد (``skin:*``) أدنى ثقة من كشوف الموديلات —
    لو كل النيغاتيفات مصدرها الجلد وثقتها تحت ``min_skin_conf`` فمش بنقبلها
    كدليل تسجيل مخالفة (بتتعرض على البث بس). ده اللي شال تكرار مخالفات
    "no mask / no hand gloves" الناتجة عن هوريستيك ضعيفة اتكررت كل فريم.
    """
    key = _norm_name(negative)
    model_confs: list[float] = []
    skin_confs: list[float] = []
    for d in detections:
        if _norm_name(d.class_name) != key:
            continue
        if is_skin_source(d.source):
            skin_confs.append(d.confidence)
        else:
            model_confs.append(d.confidence)

    candidates = list(model_confs)
    if min_skin_conf is None:
        candidates.extend(skin_confs)
    else:
        candidates.extend(c for c in skin_confs if c >= min_skin_conf)

    return max(candidates) if candidates else None


def _medical_context_conf(detections: list[Detection]) -> float:
    """
    أعلى ثقة سياق طبي **موثوق** في الكادر (بتستخدم كثقة مخالفات الغياب).

    الشخص الضعيف بيتجاهل حتى لا تُسجل مخالفات غياب بثقة بوكس متقلب.
    """
    confs = [
        d.confidence
        for d in detections
        if _norm_name(d.class_name) in _MEDICAL_CONTEXT_NAMES
        and (
            _norm_name(d.class_name) != "person"
            or d.confidence >= MIN_MEDICAL_CONTEXT_CONF
        )
    ]
    return max(confs, default=0.0)


def _overlap_ratio(inner: Detection, outer: Detection) -> float:
    ix1 = max(inner.x1, outer.x1)
    iy1 = max(inner.y1, outer.y1)
    ix2 = min(inner.x2, outer.x2)
    iy2 = min(inner.y2, outer.y2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter_area = iw * ih
    inner_area = max(1, (inner.x2 - inner.x1) * (inner.y2 - inner.y1))
    return inter_area / inner_area


def _assign_ppe_to_persons(
    persons: list[Detection],
    ppe_items: list[Detection],
    min_overlap: float = MIN_PERSON_OVERLAP,
) -> dict[int, list[Detection]]:
    """يربط كل قطعة PPE بأقرب شخص (IoU على مستطيل الشخص)."""
    assignment: dict[int, list[Detection]] = {i: [] for i in range(len(persons))}
    for item in ppe_items:
        best_idx = -1
        best_ratio = 0.0
        for i, person in enumerate(persons):
            ratio = _overlap_ratio(item, person)
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i
        if best_idx >= 0 and best_ratio >= min_overlap:
            assignment[best_idx].append(item)
    return assignment


def _assigned_names(items: list[Detection]) -> set[str]:
    return {_norm_name(item.class_name) for item in items}


class BaseViolationChecker:
    def check(
        self,
        camera_id: int,
        detections: list[Detection],
        enabled_classes: list[str] | None = None,
    ) -> list[ViolationEvent]:
        raise NotImplementedError

    def reset(self, camera_id: int) -> None:
        raise NotImplementedError


class ConstructionViolationChecker(BaseViolationChecker):
    def __init__(self, cooldown_seconds: int = 10, persist_seconds: int = 10) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.persist_seconds = persist_seconds
        self._states: dict[int, _CameraState] = {}

    def _get_state(self, camera_id: int) -> _CameraState:
        if camera_id not in self._states:
            self._states[camera_id] = _CameraState()
        return self._states[camera_id]

    def check(
        self,
        camera_id: int,
        detections: list[Detection],
        enabled_classes: list[str] | None = None,
    ) -> list[ViolationEvent]:
        profile: Profile = "construction"
        enabled_classes = sanitize_enabled_classes(profile, enabled_classes)
        state = self._get_state(camera_id)
        now = time.time()

        persons = [d for d in detections if d.class_name == "Person"]
        if not persons:
            # عندما لا يوجد أي شخص في الكادر، لا يجب أن يستمر عدّاد الغياب
            for ppe_state in state.ppe_states.values():
                ppe_state.last_seen_time = now
            return []

        ppe_items = [d for d in detections if d.class_name != "Person"]
        assignment = _assign_ppe_to_persons(persons, ppe_items)

        enabled_sorted = sorted(
            enabled_classes,
            key=lambda k: PPE_PRIORITY.index(k) if k in PPE_PRIORITY else len(PPE_PRIORITY),
        )

        violations: list[ViolationEvent] = []
        cfg_map = PPE_CLASS_MAPS["construction"]

        for ppe_key in enabled_sorted:
            cfg = cfg_map.get(ppe_key)
            if not cfg:
                continue

            label = cfg.get("label") or ppe_key
            positive = cfg.get("positive")
            negative = cfg.get("negative")

            ppe_state = state.state_for(ppe_key)

            missing_confidences: list[float] = []
            for i, person in enumerate(persons):
                assigned = assignment[i]
                assigned_names = _assigned_names(assigned)
                has_positive = bool(positive) and _norm_name(positive) in assigned_names
                # الدليل السالب لازم يكون موثوق: كشوف الجلد الضعيفة (تحت
                # SKIN_NEGATIVE_MIN_CONF) مش بتثبت "سالب" ولا بتموّل مخالفة
                neg_evidence = (
                    _violation_evidence_conf(
                        assigned,
                        str(negative),
                        min_skin_conf=settings.SKIN_NEGATIVE_MIN_CONF,
                    )
                    if negative
                    else None
                )

                is_missing = bool(neg_evidence is not None or (positive and not has_positive))
                if is_missing:
                    # لو فيه كشف سالب صريح (من الموديل أو من فلتر الجلد القوي)
                    # ثقته أدق من ثقة مستطيل الشخص
                    missing_confidences.append(
                        neg_evidence if neg_evidence is not None else person.confidence
                    )

            missing_count = len(missing_confidences)

            if missing_count == 0:
                ppe_state.last_seen_time = now
                continue

            time_missing = now - ppe_state.last_seen_time
            time_since_alert = now - ppe_state.last_alert_time

            if time_missing >= self.persist_seconds and time_since_alert >= self.cooldown_seconds:
                ppe_state.last_alert_time = now
                confidence = max(missing_confidences, default=0.0)
                violation_type = negative or f"NO-{label}"
                logger.info(
                    "Violation (construction) cam=%d type=%s count=%d",
                    camera_id,
                    violation_type,
                    missing_count,
                )
                violations.append(
                    ViolationEvent(
                        camera_id=camera_id,
                        violation_type=violation_type,
                        confidence=confidence,
                    )
                )

        return violations

    def reset(self, camera_id: int) -> None:
        self._states.pop(camera_id, None)


class MedicalViolationChecker(BaseViolationChecker):
    """
    Frame-level:
    - المخالفة لما الكلاس السالب يظهر (no mask / no hand gloves / no head cap / no goggle)
      أو عندما تغيب فئة موجبة فقط (مثل lab coat / full cover / shoe cover) مع وجود كشف في الكادر.
    - persist قصير لأن الكشف صريح
    - grace: فريم أو اثنين من غير سالب مش بيصفروا التايمر
    """

    def __init__(
        self,
        cooldown_seconds: int = 10,
        persist_seconds: int = 3,
        grace_seconds: float = 1.5,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.persist_seconds = persist_seconds
        self.grace_seconds = grace_seconds
        self._states: dict[int, _CameraState] = {}

    def _get_state(self, camera_id: int) -> _CameraState:
        if camera_id not in self._states:
            self._states[camera_id] = _CameraState()
        return self._states[camera_id]

    def check(
        self,
        camera_id: int,
        detections: list[Detection],
        enabled_classes: list[str] | None = None,
    ) -> list[ViolationEvent]:
        profile: Profile = "medical"
        enabled_classes = sanitize_enabled_classes(profile, enabled_classes)
        state = self._get_state(camera_id)
        now = time.time()

        # فايروول البروفايل الطبي: الفئات الإنشائية الخالصة (خوذة/فيست/بوت)
        # يتم تجاهلها تمامًا مهما كان مصدرها — كاميرا طبي عمرها ما تقيّم
        # معدات إنشائية، فوجود كشف زيدها في الكادر مالوش أي تأثير هنا.
        detections = [
            d
            for d in detections
            if canonical_class_name(d.class_name) not in CONSTRUCTION_ONLY_CLASSES
        ]

        cfg_map = PPE_CLASS_MAPS["medical"]
        enabled_sorted = sorted(
            enabled_classes,
            key=lambda k: PPE_PRIORITY.index(k) if k in PPE_PRIORITY else len(PPE_PRIORITY),
        )

        violations: list[ViolationEvent] = []
        medical_context = _has_medical_context(detections)
        for ppe_key in enabled_sorted:
            cfg = cfg_map.get(ppe_key)
            if not cfg:
                continue

            label = cfg.get("label") or ppe_key
            positive = cfg.get("positive")
            negative = cfg.get("negative")
            ppe_state = state.state_for(ppe_key)

            if negative:
                evidence = _violation_evidence_conf(
                    detections,
                    str(negative),
                    min_skin_conf=settings.SKIN_NEGATIVE_MIN_CONF,
                )
                is_violating = evidence is not None
                confidence = evidence if evidence is not None else 0.0
                violation_type = negative
            elif positive:
                pos_key = _norm_name(positive)
                has_positive = any(_norm_name(d.class_name) == pos_key for d in detections)
                # لا نعتبر الفئة الموجبة غائبة إلا لو فيه سياق طبي موثوق بالكادر
                # (شخص واضح من الموديل الإنشائي أو أي قطعة طبية) — مش أي كشف عشوائي
                is_violating = medical_context and not has_positive
                confidence = _medical_context_conf(detections)
                violation_type = f"no {label}"
            else:
                continue

            if is_violating:
                ppe_state.last_negative_time = now
                time_missing = now - ppe_state.last_seen_time
                time_since_alert = now - ppe_state.last_alert_time

                if time_missing >= self.persist_seconds and time_since_alert >= self.cooldown_seconds:
                    ppe_state.last_alert_time = now
                    logger.info(
                        "Violation (medical) cam=%d type=%s conf=%.2f",
                        camera_id,
                        violation_type,
                        confidence,
                    )
                    violations.append(
                        ViolationEvent(
                            camera_id=camera_id,
                            violation_type=violation_type,
                            confidence=confidence,
                        )
                    )
            else:
                if now - ppe_state.last_negative_time >= self.grace_seconds:
                    ppe_state.last_seen_time = now

        return violations

    def reset(self, camera_id: int) -> None:
        self._states.pop(camera_id, None)


ViolationChecker = ConstructionViolationChecker
