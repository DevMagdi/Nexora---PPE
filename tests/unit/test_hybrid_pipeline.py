"""
End-to-end (offline) test of the hybrid chain:

    HybridPPEDetector (stub models) → skin layer → ViolationChecker → ViolationEvent

No torch / ultralytics weights required.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.camera.manager import CameraManager
from app.core.detector import Detection
from app.core.hybrid_detector import HybridConfig, HybridPPEDetector
from app.core.ppe import canonical_class_name
from app.core.skin_analysis import hand_candidate_boxes, head_box
from app.core.violation_checker import ConstructionViolationChecker, MedicalViolationChecker

SKIN_BGR = (150, 175, 220)
DARK_BGR = (10, 10, 10)
BG_BGR = (80, 80, 80)

PERSON_BOX = (200, 40, 420, 460)


class StubDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def detect(self, frame: np.ndarray) -> list[Detection]:  # noqa: ARG002
        return [
            Detection(
                class_id=d.class_id,
                class_name=d.class_name,
                confidence=d.confidence,
                x1=d.x1,
                y1=d.y1,
                x2=d.x2,
                y2=d.y2,
                color=d.color,
                source=d.source,
            )
            for d in self._detections
        ]


def person_detection(box: tuple[int, int, int, int] = PERSON_BOX, confidence: float = 0.85) -> Detection:
    x1, y1, x2, y2 = box
    return Detection(0, "Person", confidence, x1, y1, x2, y2, (200, 200, 200))


def bare_face_scene(*, gloved_hands: bool = False) -> np.ndarray:
    """مشهد مركّب: شخص بوش مكشوف (جلد + عينين) وأيادي جلد أو قفازات."""
    frame = np.full((480, 640, 3), BG_BGR, dtype=np.uint8)
    x1, y1, x2, y2 = PERSON_BOX
    frame[y1:y2, x1:x2] = (55, 55, 55)

    hx1, hy1, hx2, hy2 = head_box(PERSON_BOX, 0.32)
    frame[hy1:hy2, hx1:hx2] = SKIN_BGR
    eye_y = hy1 + int((hy2 - hy1) * 0.42)
    eye_h = max(4, (hy2 - hy1) // 9)
    eye_w = max(4, (hx2 - hx1) // 9)
    for ratio in (0.22, 0.78):
        ex = hx1 + int((hx2 - hx1) * ratio)
        frame[eye_y : eye_y + eye_h, ex : ex + eye_w] = DARK_BGR

    hand_color = (230, 120, 60) if gloved_hands else SKIN_BGR
    for bx1, by1, bx2, by2 in hand_candidate_boxes(PERSON_BOX):
        frame[by1:by2, bx1:bx2] = hand_color
    return frame


@pytest.fixture
def hybrid() -> HybridPPEDetector:
    return HybridPPEDetector(
        StubDetector([person_detection()]),
        None,
        primary_profile="construction",
    )


def test_hybrid_chain_reports_bare_face_bare_hands_violations(hybrid):
    detections = hybrid.detect(bare_face_scene())
    names = {canonical_class_name(d.class_name) for d in detections}

    assert {"Person", "NO-Goggles", "NO-Mask", "NO-Gloves"} <= names

    checker = ConstructionViolationChecker(cooldown_seconds=0, persist_seconds=0)
    checker.check(1, detections, enabled_classes=["goggles", "mask", "gloves"])  # warm-up: يهيّئ حالة الكاميرا
    violations = checker.check(1, detections, enabled_classes=["goggles", "mask", "gloves"])

    types = {v.violation_type for v in violations}
    assert types == {"NO-Goggles", "NO-Mask", "NO-Gloves"}
    for violation in violations:
        assert violation.confidence >= 0.45
        assert violation.camera_id == 1


def test_medical_checker_accepts_hybrid_and_skin_detections(hybrid):
    detections = hybrid.detect(bare_face_scene())
    checker = MedicalViolationChecker(cooldown_seconds=0, persist_seconds=0, grace_seconds=0.0)
    checker.check(2, detections, enabled_classes=["goggles", "mask", "gloves", "coat"])  # warm-up

    violations = checker.check(2, detections, enabled_classes=["goggles", "mask", "gloves", "coat"])
    types = {v.violation_type for v in violations}

    # الفئات السالبة + البالطو الغايب (بقى ممكن لأن الهجين بيوفّر فئة Person)
    assert {"no goggle", "no mask", "no hand gloves", "no lab coat"} <= types


def test_gloved_hands_scene_does_not_report_bare_hands(hybrid):
    detections = hybrid.detect(bare_face_scene(gloved_hands=True))
    names = {canonical_class_name(d.class_name) for d in detections}

    assert "NO-Gloves" not in names
    # الوش لسه مكشوف فمخالفات الكمامة/النظارة لازم تفضل موجودة
    assert {"NO-Goggles", "NO-Mask"} <= names


def test_medical_no_head_cap_reaches_display_and_violation_checker():
    """الفئة الطبية السالبة للكاب تمرّ من الموديل الهجين للعرض والتنبيه."""
    construction = StubDetector([person_detection()])
    medical = StubDetector([Detection(8, "no head cap", 0.82, 250, 40, 370, 115, (0, 0, 255))])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
        run_construction_assist=True,
    )

    detections = hybrid.detect(bare_face_scene(), profile="medical")
    no_cap = [d for d in detections if canonical_class_name(d.class_name) == "NO-Head Cap"]
    assert len(no_cap) == 1
    assert no_cap[0].class_id == 8
    assert no_cap[0].source == "model:medical"

    manager = CameraManager({})
    displayed = manager._filter_detections_for_display("medical", ["cap"], detections)
    assert any(canonical_class_name(d.class_name) == "NO-Head Cap" for d in displayed)

    checker = MedicalViolationChecker(cooldown_seconds=0, persist_seconds=0)
    checker.check(3, detections, enabled_classes=["cap"])  # initialize the per-camera timer
    violations = checker.check(3, detections, enabled_classes=["cap"])
    assert [v.violation_type for v in violations] == ["no head cap"]
