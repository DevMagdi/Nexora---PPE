from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.detector import Detection
from app.core.violation_checker import (
    ConstructionViolationChecker,
    MedicalViolationChecker,
)


def make_detection(
    class_name: str,
    confidence: float = 0.9,
    box: tuple[int, int, int, int] = (0, 0, 100, 100),
) -> Detection:
    x1, y1, x2, y2 = box
    return Detection(
        class_id=0,
        class_name=class_name,
        confidence=confidence,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        color=(255, 0, 0),
    )


@pytest.fixture
def checker():
    return ConstructionViolationChecker(cooldown_seconds=10, persist_seconds=5)


@pytest.fixture
def medical_checker():
    return MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3, grace_seconds=1.5)


def test_no_violation_when_hardhat_present(checker):
    detections = [make_detection("Hardhat"), make_detection("Person")]
    result = checker.check(camera_id=1, detections=detections, enabled_classes=["helmet"])
    assert result == []


def test_no_violation_when_no_person(checker):
    detections = [make_detection("Hardhat")]
    result = checker.check(camera_id=1, detections=detections, enabled_classes=["helmet"])
    assert result == []


def test_empty_frame_resets_missing_timer(checker):
    camera_id = 1
    with patch("time.time", return_value=980.0):
        checker._get_state(camera_id).state_for("helmet").last_seen_time = 980.0

    # At t=995 no person is in frame -> timer should reset to 995
    with patch("time.time", return_value=995.0):
        assert checker.check(camera_id, [], enabled_classes=["helmet"]) == []

    # At t=997 (only 2s after person enters), persist_seconds=5 is not yet reached
    with patch("time.time", return_value=997.0):
        assert checker.check(camera_id, [make_detection("Person")], enabled_classes=["helmet"]) == []


def test_no_violation_before_persist_threshold(checker):
    detections = [make_detection("Person")]
    result = checker.check(camera_id=1, detections=detections, enabled_classes=["helmet"])
    assert result == []


def test_violation_after_persist_threshold(checker):
    camera_id = 1
    detections = [make_detection("Person")]

    with patch("time.time", return_value=1000.0):
        checker._get_state(camera_id).state_for("helmet").last_seen_time = 990.0
        result = checker.check(
            camera_id=camera_id, detections=detections, enabled_classes=["helmet"]
        )

    assert len(result) == 1
    assert result[0].violation_type == "NO-Hardhat"
    assert result[0].camera_id == camera_id


def test_cooldown_prevents_duplicate_alert(checker):
    camera_id = 2
    detections = [make_detection("Person")]

    with patch("time.time", return_value=1000.0):
        checker._get_state(camera_id).state_for("helmet").last_seen_time = 980.0
        first = checker.check(
            camera_id=camera_id, detections=detections, enabled_classes=["helmet"]
        )

    with patch("time.time", return_value=1005.0):
        second = checker.check(
            camera_id=camera_id, detections=detections, enabled_classes=["helmet"]
        )

    assert len(first) == 1
    assert second == []


def test_alert_fires_again_after_cooldown(checker):
    camera_id = 3
    detections = [make_detection("Person")]

    with patch("time.time", return_value=1000.0):
        checker._get_state(camera_id).state_for("helmet").last_seen_time = 980.0
        first = checker.check(
            camera_id=camera_id, detections=detections, enabled_classes=["helmet"]
        )

    with patch("time.time", return_value=1015.0):
        second = checker.check(
            camera_id=camera_id, detections=detections, enabled_classes=["helmet"]
        )

    assert len(first) == 1
    assert len(second) == 1


def test_per_camera_isolation(checker):
    detections_no_hardhat = [make_detection("Person")]
    detections_with_hardhat = [make_detection("Hardhat"), make_detection("Person")]

    with patch("time.time", return_value=1000.0):
        checker._get_state(1).state_for("helmet").last_seen_time = 980.0
        checker._get_state(2).state_for("helmet").last_seen_time = 980.0

        result_cam1 = checker.check(1, detections_no_hardhat, enabled_classes=["helmet"])
        result_cam2 = checker.check(2, detections_with_hardhat, enabled_classes=["helmet"])

    assert len(result_cam1) == 1
    assert result_cam2 == []


def test_reset_clears_state(checker):
    camera_id = 4
    checker._get_state(camera_id)
    assert camera_id in checker._states
    checker.reset(camera_id)
    assert camera_id not in checker._states


def test_medical_violation_after_persist(medical_checker):
    camera_id = 10
    dets = [make_detection("no mask", confidence=0.88)]

    with patch("time.time", return_value=1000.0):
        medical_checker._get_state(camera_id).state_for("mask").last_seen_time = 995.0
        res = medical_checker.check(camera_id, dets, enabled_classes=["mask"])

    assert len(res) == 1
    assert res[0].violation_type == "no mask"
    assert res[0].confidence == pytest.approx(0.88)


def test_medical_positive_only_class_violation(medical_checker):
    camera_id = 11
    # Staff detected (e.g. mask present) but lab coat missing
    dets = [make_detection("mask", confidence=0.92)]

    with patch("time.time", return_value=1000.0):
        medical_checker._get_state(camera_id).state_for("coat").last_seen_time = 995.0
        res = medical_checker.check(camera_id, dets, enabled_classes=["coat"])

    assert len(res) == 1
    assert res[0].violation_type == "no lab coat"


def test_construction_checker_understands_medical_style_goggle_name(checker):
    """فلتر الجلد/الموديل الطبي ممكن يبعتوا `no goggle` — لازم تتقري كـ NO-Goggles."""
    camera_id = 20
    detections = [
        make_detection("Person", box=(0, 0, 100, 300)),
        make_detection("no goggle", confidence=0.66, box=(10, 10, 60, 60)),
    ]

    with patch("time.time", return_value=1000.0):
        checker._get_state(camera_id).state_for("goggles").last_seen_time = 980.0
        result = checker.check(camera_id, detections, enabled_classes=["goggles"])

    assert len(result) == 1
    assert result[0].violation_type == "NO-Goggles"
    assert result[0].confidence == pytest.approx(0.66)


def test_medical_checker_accepts_skin_generated_no_goggles(medical_checker):
    """كشف جسر العينين بيطلع NO-Goggles (صيغة موحّدة) والـ checker لازم يفهمه."""
    camera_id = 21
    dets = [
        make_detection("Person", confidence=0.9, box=(0, 0, 200, 500)),
        make_detection("NO-Goggles", confidence=0.72, box=(10, 10, 120, 90)),
    ]

    with patch("time.time", return_value=1000.0):
        medical_checker._get_state(camera_id).state_for("goggles").last_seen_time = 995.0
        res = medical_checker.check(camera_id, dets, enabled_classes=["goggles"])

    assert len(res) == 1
    assert res[0].violation_type == "no goggle"
    assert res[0].confidence == pytest.approx(0.72)


def test_medical_positive_only_class_uses_hybrid_person_context(medical_checker):
    """الشخص بييجي من الموديل الإنشائي في النظام الهجين => يفعّل فحص غياب البالطو."""
    camera_id = 22
    dets = [make_detection("Person", confidence=0.9, box=(0, 0, 200, 500))]

    with patch("time.time", return_value=1000.0):
        medical_checker._get_state(camera_id).state_for("coat").last_seen_time = 995.0
        res = medical_checker.check(camera_id, dets, enabled_classes=["coat"])

    assert len(res) == 1
    assert res[0].violation_type == "no lab coat"


def test_medical_positive_only_class_ignores_unrelated_detections(medical_checker):
    """كشف إنشائي غير مرتبط (خوذة بدون شخص) مش دليل على وجود طاقم طبي."""
    camera_id = 23
    dets = [
        make_detection("Hardhat", confidence=0.9, box=(0, 0, 50, 50)),
        make_detection("Safety Vest", confidence=0.8, box=(0, 0, 50, 50)),
    ]

    with patch("time.time", return_value=1000.0):
        medical_checker._get_state(camera_id).state_for("coat").last_seen_time = 995.0
        res = medical_checker.check(camera_id, dets, enabled_classes=["coat"])

    assert res == []
