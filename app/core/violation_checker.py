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

# ربط عنصر PPE بالشخص بناءً على (مساحة تقاطع PPE مع بوكس الشخص) / مساحة PPE
MIN_PERSON_OVERLAP = 0.4

# ------------------------------
# Hybrid policy (1 & 2)
# ------------------------------
# 1) Negative detected -> violation after persist_seconds
# 2) Neither positive nor negative -> "Unknown" first, then violation after longer time
UNKNOWN_VIOLATION_MULTIPLIER = 2.0  # unknown_persist = persist_seconds * multiplier

# Reduce false positives: only apply "unknown -> violation" if person bbox is big enough
# (يعني الشخص قريب/واضح)
MIN_PERSON_BBOX_AREA_PX = 7000  # tune حسب 640x480 (مثلاً 7000-15000)

# Tracking (lightweight IoU-based)
TRACK_IOU_THRESHOLD = 0.3
TRACK_TTL_SECONDS = 2.0  # track expires if not seen for this long


@dataclass
class ViolationEvent:
    camera_id: int
    violation_type: str
    confidence: float
    frame_path: Optional[str] = None
    violation_id: Optional[int] = None


@dataclass
class _TrackPPEState:
    negative_start: Optional[float] = None  # when "NO-*" started being seen/decided
    unknown_start: Optional[float] = None   # when unknown started
    last_positive_time: float = 0.0         # when positive was last seen
    last_alert_time: float = 0.0            # cooldown per PPE per person(track)


@dataclass
class _PersonTrack:
    track_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    last_seen: float = field(default_factory=time.time)
    ppe: dict[str, _TrackPPEState] = field(default_factory=dict)

    def bbox_area(self) -> int:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)

    def state_for(self, ppe_key: str) -> _TrackPPEState:
        if ppe_key not in self.ppe:
            self.ppe[ppe_key] = _TrackPPEState()
        return self.ppe[ppe_key]


@dataclass
class _CameraState:
    next_track_id: int = 1
    tracks: dict[int, _PersonTrack] = field(default_factory=dict)


def _overlap_ratio(inner: Detection, outer: Detection) -> float:
    """(intersect(inner, outer) area) / (inner area)"""
    ix1 = max(inner.x1, outer.x1)
    iy1 = max(inner.y1, outer.y1)
    ix2 = min(inner.x2, outer.x2)
    iy2 = min(inner.y2, outer.y2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter_area = iw * ih

    inner_area = max(1, (inner.x2 - inner.x1) * (inner.y2 - inner.y1))
    return inter_area / inner_area


def _iou(a: Detection | _PersonTrack, b: Detection | _PersonTrack) -> float:
    ax1, ay1, ax2, ay2 = a.x1, a.y1, a.x2, a.y2
    bx1, by1, bx2, by2 = b.x1, b.y1, b.x2, b.y2

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = max(1, area_a + area_b - inter)
    return inter / union


def _assign_ppe_to_persons(
    persons: list[Detection],
    ppe_items: list[Detection],
    min_overlap: float = MIN_PERSON_OVERLAP,
) -> dict[int, dict[str, float]]:
    """
    Assign each PPE item to ONE best person (highest overlap ratio).
    Returns: {person_index: {class_name: max_confidence}}
    """
    assignment: dict[int, dict[str, float]] = {i: {} for i in range(len(persons))}

    for item in ppe_items:
        best_idx = -1
        best_ratio = 0.0

        for i, person in enumerate(persons):
            ratio = _overlap_ratio(item, person)
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i

        if best_idx >= 0 and best_ratio >= min_overlap:
            prev = assignment[best_idx].get(item.class_name, 0.0)
            assignment[best_idx][item.class_name] = max(prev, float(item.confidence))

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

    def _update_tracks(self, state: _CameraState, persons: list[Detection], now: float) -> dict[int, int]:
        """
        IoU match current persons to existing tracks.
        Returns mapping: {person_index: track_id}
        """
        # expire old tracks
        expired = [tid for tid, tr in state.tracks.items() if now - tr.last_seen > TRACK_TTL_SECONDS]
        for tid in expired:
            state.tracks.pop(tid, None)

        track_ids = list(state.tracks.keys())
        used_tracks: set[int] = set()
        mapping: dict[int, int] = {}

        for pi, person in enumerate(persons):
            best_tid = None
            best_score = 0.0

            for tid in track_ids:
                if tid in used_tracks:
                    continue
                tr = state.tracks[tid]
                score = _iou(person, tr)
                if score > best_score:
                    best_score = score
                    best_tid = tid

            if best_tid is not None and best_score >= TRACK_IOU_THRESHOLD:
                # update track bbox
                tr = state.tracks[best_tid]
                tr.x1, tr.y1, tr.x2, tr.y2 = person.x1, person.y1, person.x2, person.y2
                tr.last_seen = now
                mapping[pi] = best_tid
                used_tracks.add(best_tid)
            else:
                # create new track
                tid = state.next_track_id
                state.next_track_id += 1
                state.tracks[tid] = _PersonTrack(
                    track_id=tid,
                    x1=person.x1,
                    y1=person.y1,
                    x2=person.x2,
                    y2=person.y2,
                    last_seen=now,
                )
                mapping[pi] = tid
                used_tracks.add(tid)

        return mapping

    def check(
        self,
        camera_id: int,
        detections: list[Detection],
        enabled_classes: Optional[list[str]] = None,
    ) -> list[ViolationEvent]:
        enabled_classes = sanitize_enabled_classes(enabled_classes)
        state = self._get_state(camera_id)
        now = time.time()

        persons = [d for d in detections if d.class_name == "Person"]
        if not persons:
            return []

        # track persons
        person_to_track = self._update_tracks(state, persons, now)

        # assign PPE items to persons
        ppe_items = [d for d in detections if d.class_name != "Person"]
        assignment = _assign_ppe_to_persons(persons, ppe_items)

        enabled_sorted = sorted(
            enabled_classes,
            key=lambda k: PPE_PRIORITY.index(k) if k in PPE_PRIORITY else len(PPE_PRIORITY),
        )

        violations: list[ViolationEvent] = []
        unknown_persist = self.persist_seconds * UNKNOWN_VIOLATION_MULTIPLIER

        for ppe_key in enabled_sorted:
            cfg = PPE_CLASS_MAP.get(ppe_key)
            if not cfg:
                continue

            label = cfg.get("label") or ppe_key
            positive = cfg.get("positive")
            negative = cfg.get("negative")
            if positive is None and negative is None:
                continue

            # check per person(track)
            for i, person in enumerate(persons):
                tid = person_to_track[i]
                track = state.tracks.get(tid)
                if not track:
                    continue

                tr_state = track.state_for(ppe_key)
                assigned = assignment.get(i, {})

                pos_conf = float(assigned.get(positive, 0.0)) if positive else 0.0
                neg_conf = float(assigned.get(negative, 0.0)) if negative else 0.0

                has_positive = bool(positive) and pos_conf > 0
                has_negative = bool(negative) and neg_conf > 0

                # ---- update state machine ----
                if has_positive:
                    tr_state.last_positive_time = now
                    tr_state.negative_start = None
                    tr_state.unknown_start = None
                    continue

                if has_negative:
                    # confirmed violation path
                    if tr_state.negative_start is None:
                        tr_state.negative_start = now
                    tr_state.unknown_start = None
                else:
                    # unknown path (no positive, no negative)
                    tr_state.negative_start = None
                    if tr_state.unknown_start is None:
                        tr_state.unknown_start = now

                # ---- decide alerts with persist + cooldown ----
                time_since_alert = now - tr_state.last_alert_time
                if time_since_alert < self.cooldown_seconds:
                    continue

                # (1) negative-based violation
                if tr_state.negative_start is not None:
                    if now - tr_state.negative_start >= self.persist_seconds:
                        tr_state.last_alert_time = now
                        vtype = negative or f"NO-{label}"
                        violations.append(
                            ViolationEvent(
                                camera_id=camera_id,
                                violation_type=vtype,
                                confidence=neg_conf or float(person.confidence),
                            )
                        )
                        continue

                # (2) unknown -> violation (after longer time) ONLY if person is large enough
                if tr_state.unknown_start is not None:
                    if track.bbox_area() < MIN_PERSON_BBOX_AREA_PX:
                        continue  # too far / too small => don't accuse
                    # don't accuse if recently saw positive
                    if tr_state.last_positive_time and (now - tr_state.last_positive_time) < self.persist_seconds:
                        continue
                    if now - tr_state.unknown_start >= unknown_persist:
                        tr_state.last_alert_time = now
                        vtype = negative or f"NO-{label}"
                        violations.append(
                            ViolationEvent(
                                camera_id=camera_id,
                                violation_type=vtype,
                                confidence=float(person.confidence),
                            )
                        )

        # log (summary)
        for v in violations:
            logger.info("Violation on camera %d: %s", camera_id, v.violation_type)

        return violations

    def reset(self, camera_id: int) -> None:
        self._states.pop(camera_id, None)