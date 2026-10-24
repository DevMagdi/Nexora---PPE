from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.config import settings
from app.core.detector import Detection
from app.core.postprocess import resolve_ppe_conflicts
from app.core.ppe import PPE_CLASSES, canonical_class_name, sanitize_enabled_classes


def apply_persist_floor(persist_seconds: int, floor_seconds: int) -> int:
    return max(persist_seconds, floor_seconds)


@dataclass
class ViolationEvent:
    camera_id: int
    violation_type: str
    confidence: float
    frame_path: str | None = None
    violation_id: int | None = None


@dataclass
class _RuleState:
    first_seen: float
    last_seen: float
    last_alert: float = float("-inf")


class ViolationChecker:
    """Alert only on sustained, explicit model evidence, never on an unseen item.

    Timers are per camera/rule (not identities). A gap or a clean frame resets
    persistence. Counts are detection events, not unique workers or compliance %.
    """

    def __init__(self, cooldown_seconds: int = 60, persist_seconds: int = 8) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.persist_seconds = persist_seconds
        self._states: dict[tuple[int, str], _RuleState] = {}

    def check(
        self,
        camera_id: int,
        detections: list[Detection],
        enabled_classes: list[str] | None = None,
        supported_negative_rules: frozenset[str] | None = None,
    ) -> list[ViolationEvent]:
        enabled = sanitize_enabled_classes(enabled_classes)
        detections = resolve_ppe_conflicts(detections)
        threshold = max(settings.DETECTION_CONFIDENCE, settings.DETECTION_NEGATIVE_CONFIDENCE)
        now = time.monotonic()
        events: list[ViolationEvent] = []
        for key in enabled:
            if supported_negative_rules is not None and key not in supported_negative_rules:
                self._states.pop((camera_id, key), None)
                continue
            negative = PPE_CLASSES[key]["negative"]
            confidence = max(
                (
                    d.confidence
                    for d in detections
                    if canonical_class_name(d.class_name) == negative
                    and d.source == "model"
                    and d.confidence >= threshold
                ),
                default=0.0,
            )
            state_key = (camera_id, key)
            state = self._states.get(state_key)
            if not confidence:
                if state:
                    state.first_seen = float("inf")
                continue
            if state is None:
                state = _RuleState(now, now)
                self._states[state_key] = state
            elif (
                state.first_seen == float("inf")
                or now - state.last_seen > settings.CAMERA_FRAME_STALE_SECONDS
            ):
                state.first_seen = now
            state.last_seen = now
            if (
                now - state.first_seen >= self.persist_seconds
                and now - state.last_alert >= self.cooldown_seconds
            ):
                state.last_alert = now
                events.append(ViolationEvent(camera_id, negative, confidence))
        return events

    def reset(self, camera_id: int) -> None:
        for key in [key for key in self._states if key[0] == camera_id]:
            self._states.pop(key, None)
