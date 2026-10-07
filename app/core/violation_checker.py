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


@dataclass
class ViolationEvent:
    camera_id: int
    violation_type: str
    confidence: float
    frame_path: Optional[str] = None


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
        frame_path: Optional[str] = None,
    ) -> Optional[ViolationEvent]:
        enabled_classes = sanitize_enabled_classes(enabled_classes)
        state = self._get_state(camera_id)
        now = time.time()

        # لازم Person يكون موجود عشان نبدأ نحسب مخالفة PPE
        if not any(d.class_name == "Person" for d in detections):
            return None

        detected_names = {d.class_name for d in detections}

        enabled_sorted = sorted(
            enabled_classes,
            key=lambda k: PPE_PRIORITY.index(k) if k in PPE_PRIORITY else 999,
        )

        for ppe_key in enabled_sorted:
            cfg = PPE_CLASS_MAP.get(ppe_key)
            if not cfg:
                continue

            label = cfg.get("label") or ppe_key
            positive = cfg.get("positive")
            negative = cfg.get("negative")

            # لو الاتنين None يبقى مفيش حاجة نقدر نعملها
            if positive is None and negative is None:
                continue

            ppe_state = state.state_for(ppe_key)

            # تحديث آخر وقت ظهر فيه الـ PPE (positive)
            if positive and positive in detected_names:
                ppe_state.last_seen_time = now

            # تحديد إن كان Missing:
            # - لو negative موجود في detections => Missing مؤكد
            # - لو negative مش موجود أو None => نعتمد على غياب positive
            is_missing = False
            if negative and negative in detected_names:
                is_missing = True
            elif positive:
                # لو الـ positive مش ظاهر في الفريم => Missing (حتى لو مفيش negative class)
                if positive not in detected_names:
                    is_missing = True

            if not is_missing:
                continue

            time_missing = now - ppe_state.last_seen_time
            time_since_alert = now - ppe_state.last_alert_time

            if time_missing >= self.persist_seconds and time_since_alert >= self.cooldown_seconds:
                ppe_state.last_alert_time = now

                # confidence مرجعية: أعلى confidence ل Person
                confidence = max(
                    (d.confidence for d in detections if d.class_name == "Person"),
                    default=0.0,
                )

                # نوع المخالفة:
                # - لو عندنا negative class في الموديل استخدمها (NO-Hardhat..)
                # - لو مفيش negative (زي Gloves غالبًا) نكوّن NO-<label>
                violation_type = negative or f"NO-{label}"

                logger.info("Violation on camera %d: %s", camera_id, violation_type)
                return ViolationEvent(
                    camera_id=camera_id,
                    violation_type=violation_type,
                    confidence=confidence,
                    frame_path=frame_path,
                )

        return None

    def reset(self, camera_id: int) -> None:
        self._states.pop(camera_id, None)