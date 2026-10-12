"""
اختبارات حراس الدقة (Precision Guards) + فايروول البروفايل الطبي.

مستوحاة من مشاكل لوج 2026-10-12 الفعلي:

* كاميرا طبية (webcam) كانت تطلّع ``NO-Mask`` صناعي بثقة 0.96 و
  ``NO-Gloves`` بـ 0.59-0.75 على كل فريم → مخالفات متكررة على دليل ضعيف.
* إعدادات ثقة منخفضة أوي (global 0.05/0.10) بتنتج بوكس Person متقلب.
* كاميرا طبية لازم عمرها ما تقول "ناقص خوذة" (أو أي فئة إنشائية خالصة).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.detector import Detection, apply_confidence_floor, is_skin_source
from app.core.hybrid_detector import HybridConfig, HybridPPEDetector
from app.core.violation_checker import (
    ConstructionViolationChecker,
    MedicalViolationChecker,
    apply_persist_floor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_detection(
    class_name: str,
    confidence: float = 0.9,
    box: tuple[int, int, int, int] = (0, 0, 100, 100),
    source: str = "model",
) -> Detection:
    x1, y1, x2, y2 = box
    return Detection(
        class_id=-1 if source.startswith("skin:") else 0,
        class_name=class_name,
        confidence=confidence,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        color=(255, 0, 0),
        source=source,
    )


class StubDetector:
    """موديل وهمي بيرجع كشوف ثابتة (بدون torch/ultralytics)."""

    def __init__(self, detections: list[Detection]) -> None:
        self.detections = detections
        self.class_names = {0: "stub"}

    def detect(self, frame) -> list[Detection]:  # noqa: ANN001
        return list(self.detections)


# ---------------------------------------------------------------------------
# 1) أرضية الثقة (DETECTION_CONFIDENCE_FLOOR)
# ---------------------------------------------------------------------------


def test_confidence_floor_raises_low_global_and_class_thresholds():
    conf, class_map = apply_confidence_floor(
        0.05, {2: 0.7, 7: 0.15, 9: 0.30}, 0.25, model_label="test.pt"
    )
    assert conf == pytest.approx(0.25)
    # العتبات العالية زي ما هي
    assert class_map[2] == pytest.approx(0.7)
    assert class_map[9] == pytest.approx(0.30)
    # العتبات الواطية اترفعت للأرضية
    assert class_map[7] == pytest.approx(0.25)


def test_confidence_floor_keeps_high_values_untouched():
    conf, class_map = apply_confidence_floor(0.6, {5: 0.7}, 0.25)
    assert conf == pytest.approx(0.6)
    assert class_map == {5: pytest.approx(0.7)}


def test_ppdetector_applies_floor_from_settings():
    """إعدادات واطية زي لوج المستخدم (global 0.05) بتترفع تلقائيًا عند التحميل."""
    fake_ultralytics = MagicMock()
    fake_model = MagicMock()
    fake_model.names = {0: "mask", 1: "no mask"}
    fake_ultralytics.YOLO.return_value = fake_model

    settings = Settings(
        _env_file=None,
        MEDICAL_DETECTION_CONFIDENCE=0.05,
        MEDICAL_CLASS_CONF_THRESHOLDS="1:0.10",
        DETECTION_CONFIDENCE_FLOOR=0.25,
    )

    with (
        patch.dict("sys.modules", {"ultralytics": fake_ultralytics}),
        patch("app.core.detector.settings", settings),
        patch("app.core.detector.require_model_file", return_value="Model/x.pt"),
    ):
        from app.core.detector import PPEDetector

        detector = PPEDetector(
            "Model/x.pt",
            confidence=settings.MEDICAL_DETECTION_CONFIDENCE,
            default_class_conf=0.10,
            class_conf_thresholds=settings.MEDICAL_CLASS_CONF_THRESHOLDS,
        )

    assert detector.confidence == pytest.approx(0.25)
    assert detector.class_conf[1] == pytest.approx(0.25)
    assert detector.default_class_conf == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# 2) دلالات مصدر الجلد (is_skin_source)
# ---------------------------------------------------------------------------


def test_is_skin_source_only_for_skin_generated_detections():
    # مولَّد بالجلد خالص
    assert is_skin_source("skin:mouth") is True
    assert is_skin_source("skin:distance_transform") is True
    # موديل اتأكّد بالجلد — يفضل كشف موديل بثقته الكاملة
    assert is_skin_source("model:construction+skin:mouth") is False
    assert is_skin_source("model") is False
    assert is_skin_source(None) is False


# ---------------------------------------------------------------------------
# 3) دليل الجلد الضعيف مش بيسجّل مخالفات
# ---------------------------------------------------------------------------


def _seed_and_check(medical_checker, cam, ppe_key, detections, *, now=1004.0, last_seen=1000.0):
    """يزرع مؤقت الحالة زي نمط الاختبارات الموجودة وبعدين يفحص فريم واحد."""
    with patch("time.time", return_value=now):
        medical_checker._get_state(cam).state_for(ppe_key).last_seen_time = last_seen
        return medical_checker.check(cam, detections, enabled_classes=[ppe_key])


def test_weak_skin_negative_does_not_create_medical_violation():
    """NO-Mask صناعي بثقة 0.65 (زي skin:mouth الواطية في اللوج) → مفيش مخالفة."""
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    detections = [
        make_detection("Person", 0.85),
        make_detection("NO-Mask", 0.65, source="skin:mouth"),
    ]
    assert _seed_and_check(checker, 7, "mask", detections) == []


def test_strong_skin_negative_still_creates_medical_violation():
    """دليل جلد قوي (≥ 0.70) لسه بيسجّل مخالفة عادي."""
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    detections = [
        make_detection("Person", 0.85),
        make_detection("NO-Mask", 0.75, source="skin:mouth"),
    ]
    violations = _seed_and_check(checker, 7, "mask", detections)
    assert len(violations) == 1
    assert violations[0].violation_type == "no mask"


def test_model_negative_creates_medical_violation_regardless_of_skin_floor():
    """كشف موديل (source=model) بيثبت مخالفة حتى بثقة أقل من أرضية الجلد."""
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    detections = [
        make_detection("Person", 0.85),
        make_detection("NO-Mask", 0.55, source="model:medical"),
    ]
    violations = _seed_and_check(checker, 7, "mask", detections)
    assert len(violations) == 1
    assert violations[0].confidence == pytest.approx(0.55)


def test_model_confirmed_by_skin_keeps_full_evidence():
    """``model+skin`` = كشف موديل مؤكَّد — مش بيتأثر بأرضية الجلد."""
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    detections = [
        make_detection("Person", 0.85),
        make_detection("NO-Mask", 0.6, source="model:construction+skin:mouth"),
    ]
    violations = _seed_and_check(checker, 7, "mask", detections)
    assert len(violations) == 1


def test_construction_weak_skin_negative_not_used_as_evidence():
    """
    في الإنشاءات غياب الموجب هو مُطلق المخالفة (بالـ persist) — بس دليل الجلد
    الضعيف مش بيتستخدم كثقة للمخالفة؛ الثقة بترجع لبوكس الشخص الموثوق.
    """
    checker = ConstructionViolationChecker(cooldown_seconds=10, persist_seconds=5)
    detections = [
        make_detection("Person", 0.9),
        make_detection("NO-Goggles", 0.5, source="skin:eye_bridge"),
    ]
    with patch("time.time", return_value=1000.0):
        checker._get_state(1).state_for("goggles").last_seen_time = 980.0
        violations = checker.check(1, detections, enabled_classes=["goggles"])
    # المخالفة اتسجلت بسبب غياب الـ Goggles الموجب، وثقتها من الشخص (0.9)
    # مش من الهوريستيك الواطي (0.5)
    assert len(violations) == 1
    assert violations[0].confidence == pytest.approx(0.9)


def test_construction_strong_skin_negative_used_as_evidence():
    """جلد قوي (≥ 0.70) بيفضل دليل مخالفة صحيح وثقته هي اللي تتسجل."""
    checker = ConstructionViolationChecker(cooldown_seconds=10, persist_seconds=5)
    detections = [
        make_detection("Person", 0.9),
        make_detection("NO-Goggles", 0.8, source="skin:eye_bridge"),
    ]
    with patch("time.time", return_value=1000.0):
        checker._get_state(1).state_for("goggles").last_seen_time = 980.0
        violations = checker.check(1, detections, enabled_classes=["goggles"])
    assert len(violations) == 1
    assert violations[0].violation_type == "NO-Goggles"
    assert violations[0].confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# 4) السياق الطبي الموثوق (مخالفات الغياب)
# ---------------------------------------------------------------------------


def test_weak_person_does_not_trigger_absence_violation():
    """Person متقلب بـ 0.26 أو 0.41 (زي اللوج) مش بيثبت 'ناقص بالطو'."""
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    assert _seed_and_check(checker, 3, "coat", [make_detection("Person", 0.26, source="model:construction")]) == []
    assert _seed_and_check(checker, 4, "coat", [make_detection("Person", 0.41, source="model:construction")]) == []


def test_negative_face_only_or_closeup_webcam_does_not_trigger_lab_coat():
    """
    إصلاح المشكلة #4: ظهور no mask وحده أو لقطة وجه قريبة على Webcam (حيث يغطي
    الوجه >= 55% من ارتفاع مستطيل الشخص) لا يسجّل مخالفة no lab coat.
    """
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    # 1) no mask فقط بدون شخص أو قطعة موجبة
    assert _seed_and_check(checker, 4, "coat", [make_detection("NO-Mask", 0.91, source="model:construction")]) == []
    # 2) لقطة وجه قريبة (Person بارتفاع 200 و NO-Mask بارتفاع 140 = 70% من الشخص)
    closeup = [
        make_detection("Person", 0.85, box=(100, 50, 400, 250), source="model:construction"),
        make_detection("NO-Mask", 0.91, box=(140, 60, 360, 200), source="model:construction"),
    ]
    assert _seed_and_check(checker, 5, "coat", closeup) == []


def test_lab_coat_absence_uses_person_confidence_not_no_mask_confidence():
    """إصلاح المشكلة #4: ثقة no lab coat تأتي من Person (0.68) وليس من NO-Mask (0.91)."""
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    detections = [
        make_detection("Person", 0.68, box=(100, 20, 420, 460), source="model:construction"),
        make_detection("NO-Mask", 0.91, box=(180, 40, 320, 120), source="model:construction"),
    ]
    violations = _seed_and_check(checker, 6, "coat", detections)
    assert len(violations) == 1
    assert violations[0].violation_type == "no lab coat"
    assert violations[0].confidence == pytest.approx(0.68)


def test_persist_floor_and_medical_absence_persist_window():
    """إصلاح المشكلة #4: رفع VIOLATION_PERSIST_SECONDS القديم (3 ثوانٍ) إلى الأرضية (8 ثوانٍ)."""
    assert apply_persist_floor(3, 8) == 8
    assert apply_persist_floor(10, 8) == 10

    checker = MedicalViolationChecker(
        cooldown_seconds=10,
        persist_seconds=3,
        absence_persist_seconds=8,
    )
    detections = [
        make_detection("Person", 0.80, box=(100, 20, 420, 460), source="model:construction"),
        make_detection("NO-Mask", 0.91, box=(180, 40, 320, 120), source="model:medical"),
    ]
    # بعد 4 ثوانٍ: الكشف السالب الصريح (no mask) يسجّل مخالفة، بينما غياب البالطو ينتظر 8 ثوانٍ
    with patch("time.time", return_value=1004.0):
        checker._get_state(8).state_for("mask").last_seen_time = 1000.0
        checker._get_state(8).state_for("coat").last_seen_time = 1000.0
        v_early = checker.check(8, detections, enabled_classes=["mask", "coat"])
    assert [v.violation_type for v in v_early] == ["no mask"]

    # بعد 8 ثوانٍ: غياب البالطو المستمر يسجّل مخالفته
    with patch("time.time", return_value=1008.0):
        v_late = checker.check(8, detections, enabled_classes=["mask", "coat"])
    assert [v.violation_type for v in v_late] == ["no lab coat"]


def test_strong_person_triggers_absence_violation():
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=3)
    detections = [make_detection("Person", 0.8, source="model:construction")]
    violations = _seed_and_check(checker, 3, "coat", detections)
    assert len(violations) == 1
    assert violations[0].violation_type == "no lab coat"
    assert violations[0].confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# 5) فايروول البروفايل الطبي — عمرها ما تقول "ناقص خوذة"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "construction_class",
    ["Hardhat", "NO-Hardhat", "Safety Vest", "NO-Safety Vest", "Safety Boots", "NO-Safety Boots"],
)
def test_medical_checker_completely_ignores_construction_only_classes(construction_class):
    """حتى لو كشف إنشائي وصل للـ checker بكثافة عالية → صفر مخالفات منه."""
    checker = MedicalViolationChecker(cooldown_seconds=10, persist_seconds=1)
    detections = [
        make_detection(construction_class, 0.99),
        make_detection("Person", 0.9),
    ]
    with patch("time.time", return_value=1000.0):
        first = checker.check(9, detections, enabled_classes=["mask", "cap", "goggles", "gloves"])
    with patch("time.time", return_value=1002.0):
        second = checker.check(9, detections, enabled_classes=["mask", "cap", "goggles", "gloves"])
    assert first == [] and second == []


def test_hybrid_medical_profile_drops_construction_only_from_any_source():
    """الفايروول النهائي في الهجين: مفيش فئة إنشائية من أي مصدر تعدي لكاميرا طبي."""
    hybrid = HybridPPEDetector(
        StubDetector([]),
        StubDetector(
            [
                # كشف إنشائي جاي من مصدر "طبي" (سيناريو مستحيل عمليًا — بس الفايروول
                # لازم يمسكه برضه) + كشف طبي سليم
                make_detection("NO-Hardhat", 0.95, source="model:medical"),
                make_detection("Mask", 0.9, source="model:medical"),
            ]
        ),
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
        run_construction_assist=False,
    )

    out = hybrid.detect(None, profile="medical")
    names = {d.class_name for d in out}
    assert "Mask" in names
    assert "NO-Hardhat" not in names
    assert not names & {"Hardhat", "NO-Hardhat", "Safety Vest", "NO-Safety Vest", "Safety Boots", "NO-Safety Boots"}


# ---------------------------------------------------------------------------
# 6) سقف ثقة الكشوف الصناعية + بوابة الشخص الموثوق
# ---------------------------------------------------------------------------


def test_skin_confidence_is_capped_by_synthetic_max():
    """الهوريستيك مش بيدّعي 0.96 زي اللوج — السقف 0.85."""
    hybrid = HybridPPEDetector(
        None,
        None,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
    )
    assert hybrid._skin_confidence(0.99) == pytest.approx(0.85)
    assert hybrid._skin_confidence(0.96) == pytest.approx(0.85)
    # والأرضية زي ما هي
    assert hybrid._skin_confidence(0.10) == pytest.approx(0.45)


def test_default_config_carries_precision_guards():
    cfg = HybridConfig.from_settings()
    assert cfg.synthetic_max_conf == pytest.approx(Settings(_env_file=None).SKIN_SYNTHETIC_MAX_CONF)
    assert cfg.skin_negative_min_conf == pytest.approx(Settings(_env_file=None).SKIN_NEGATIVE_MIN_CONF)
    assert cfg.skin_min_person_conf == pytest.approx(Settings(_env_file=None).SKIN_MIN_PERSON_CONF)
    assert cfg.positive_override_min_conf > cfg.positive_override_max_conf
