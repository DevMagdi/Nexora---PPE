from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from app.core.detector import Detection
from app.core.logging import get_logger
from app.core.ppe import PPE_CLASS_MAP, sanitize_enabled_classes

logger = get_logger(__name__)

# ترتيب أولوية فحص المخالفات عند تفعيل أكثر من PPE في نفس الكاميرا
PPE_PRIORITY: list[str] = ["helmet", "vest", "mask", "gloves", "goggles", "boots", "coat"]

# نسبة التداخل المطلوبة عشان نعتبر عنصر PPE (خوذة/سترة...) تابع لشخص معيّن.
# بنحسبها كـ (مساحة تقاطع عنصر الـ PPE مع بوكس الشخص) ÷ (مساحة عنصر الـ PPE نفسه)
# مش IoU عادي، لأن بوكس الخوذة غالبًا أصغر بكتير من بوكس الشخص بالكامل،
# فـ IoU هيطلع صغير جدًا حتى لو الخوذة فعلاً على راس الشخص ده بالظبط.
MIN_PERSON_OVERLAP = 0.4


@dataclass
class ViolationEvent:
    camera_id: int
    violation_type: str
    confidence: float
    frame_path: Optional[str] = None
    # ✅ بيتحدد بعد ما نحفظ المخالفة في قاعدة البيانات (app.db.repository
    # .save_violation)، عشان الـ AlertDispatcher يقدر يربط كل محاولة
    # إرسال تنبيه بالـ violation الصحيحة في جدول alert_log.
    violation_id: Optional[int] = None


@dataclass
class _PPEState:
    last_seen_time: float = field(default_factory=time.time)
    last_alert_time: float = 0.0


@dataclass
class _CameraState:
    ppe_states: dict[str, _PPEState] = field(default_factory=dict)

    def state_for(self, ppe_key: str) -> _PPEState:
        if ppe_key not in self.ppe_states:
            self.ppe_states[ppe_key] = _PPEState()
        return self.ppe_states[ppe_key]


def _overlap_ratio(inner: Detection, outer: Detection) -> float:
    """نسبة مساحة `inner` اللي واقعة جوه `outer`. مش IoU متماثل (asymmetric)."""
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
) -> dict[int, set[str]]:
    """
    يربط كل عنصر PPE (خوذة/سترة/إلخ) بأقرب شخص ليه (أعلى نسبة تداخل)،
    مش بكل شخص متداخل معاه فوق الحد — عشان عنصر واحد ميتحسبش لشخصين
    لو كانوا واقفين قريبين من بعض.

    Args:
        persons: الأشخاص المكتشفين (class_name == "Person").
        ppe_items: عناصر الـ PPE المكتشفة (كل حاجة غير "Person").
        min_overlap: أقل نسبة تداخل (0-1) عشان نعتبر الربط صحيح.

    Returns:
        dict: {person_index: set(class_names المرتبطة بيه)}
        مثال: {0: {"Hardhat", "Safety Vest"}, 1: {"NO-Hardhat"}}
    """
    assignment: dict[int, set[str]] = {i: set() for i in range(len(persons))}

    for item in ppe_items:
        best_idx = -1
        best_ratio = 0.0
        for i, person in enumerate(persons):
            ratio = _overlap_ratio(item, person)
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i

        if best_idx >= 0 and best_ratio >= min_overlap:
            assignment[best_idx].add(item.class_name)

    return assignment


class ViolationChecker:
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
        enabled_classes: Optional[list[str]] = None,
    ) -> list[ViolationEvent]:
        """
        يفحص كل شخص مكتشف لوحده (مش الفريم ككل)، فشخص واحد لابس خوذة
        متبقاش بتغطي على باقي العمال اللي من غيرها في نفس الفريم.

        ⚠️ حد معروف: بدون Person Tracking (track_id ثابت بين الفريمات)،
        "استمرارية الغياب" بتتقاس على مستوى "هل فيه دايمًا شخص واحد ناقص
        PPE معيّن طوال نافذة الـ persist" مش على مستوى "نفس الشخص بعينه".
        ده تقريب مقبول عمليًا، لكن الدقة الكاملة للفرد الواحد محتاجة
        Person Tracking (موضوع منفصل في خطة التطوير).
        """
        enabled_classes = sanitize_enabled_classes(enabled_classes)
        state = self._get_state(camera_id)
        now = time.time()

        persons = [d for d in detections if d.class_name == "Person"]
        if not persons:
            return []

        ppe_items = [d for d in detections if d.class_name != "Person"]
        assignment = _assign_ppe_to_persons(persons, ppe_items)

        enabled_sorted = sorted(
            enabled_classes,
            key=lambda k: PPE_PRIORITY.index(k) if k in PPE_PRIORITY else len(PPE_PRIORITY),
        )

        violations: list[ViolationEvent] = []

        for ppe_key in enabled_sorted:
            cfg = PPE_CLASS_MAP.get(ppe_key)
            if not cfg:
                continue

            label = cfg.get("label") or ppe_key
            positive = cfg.get("positive")
            negative = cfg.get("negative")

            if positive is None and negative is None:
                continue

            ppe_state = state.state_for(ppe_key)

            # الفحص الجوهري: نمر على كل شخص لوحده، مش على مجموعة
            # الـ class names بتاعة الفريم كله.
            missing_confidences: list[float] = []
            for i, person in enumerate(persons):
                assigned_names = assignment[i]

                has_positive = bool(positive) and positive in assigned_names
                has_negative = bool(negative) and negative in assigned_names

                is_missing = False
                if has_negative:
                    is_missing = True
                elif positive and not has_positive:
                    is_missing = True

                if is_missing:
                    missing_confidences.append(person.confidence)

            missing_count = len(missing_confidences)

            if missing_count == 0:
                # كل الأشخاص ملتزمين بالـ PPE ده في الفريم الحالي
                ppe_state.last_seen_time = now
                continue

            time_missing = now - ppe_state.last_seen_time
            time_since_alert = now - ppe_state.last_alert_time

            if time_missing >= self.persist_seconds and time_since_alert >= self.cooldown_seconds:
                ppe_state.last_alert_time = now

                confidence = max(missing_confidences, default=0.0)
                violation_type = negative or f"NO-{label}"

                logger.info(
                    "Violation on camera %d: %s (%d person(s) missing)",
                    camera_id, violation_type, missing_count,
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