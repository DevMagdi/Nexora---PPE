"""
اختبارات الجسر الإنشائي للبروفايل الطبي (construction → medical bridge).

لما كاميرا طبية بتستعين بالموديل الإنشائي (اللي بيوفر فئة ``Person`` الناقصة
في الموديل الطبي)، الجسر بيعدي بس الكشوف اللي تفيد البروفايل الطبي: الشخص +
القطع المشتركة (كمامة/نظارة/جوانتي). الفئات الإنشائية الخالصة (خوذة/فيست/بوت)
لازم تسقط قبل ما توصل للعدادات أو فاحص المخالفات.
"""

from __future__ import annotations

import numpy as np

from app.core.detector import Detection
from app.core.hybrid_detector import HybridConfig, HybridPPEDetector
from app.core.ppe import canonical_class_name
from app.core.violation_checker import MedicalViolationChecker

PERSON_BOX = (200, 40, 420, 460)


def det(
    class_name: str,
    box: tuple[int, int, int, int],
    confidence: float = 0.8,
    source: str = "model",
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
        source=source,
    )


class StubDetector:
    """موديل وهمي بترجع كشوف ثابتة (بدون torch/ultralytics)."""

    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections
        self.calls = 0
        self.names: dict[int, str] = {}
        self.class_names: dict[int, str] = {}

    def detect(self, frame: np.ndarray) -> list[Detection]:  # noqa: ARG002
        self.calls += 1
        return [
            det(d.class_name, (d.x1, d.y1, d.x2, d.y2), d.confidence, d.source)
            for d in self._detections
        ]


def frame() -> np.ndarray:
    return np.full((480, 640, 3), 90, dtype=np.uint8)


def make_hybrid(construction: StubDetector, medical: StubDetector) -> HybridPPEDetector:
    return HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
        run_construction_assist=True,
    )


def test_medical_profile_keeps_shared_construction_classes():
    construction = StubDetector(
        [
            det("Person", PERSON_BOX),
            det("Mask", (250, 60, 330, 130), 0.7),
            det("Goggles", (240, 50, 340, 100), 0.6),
            det("Gloves", (210, 300, 260, 380), 0.6),
        ]
    )
    hybrid = make_hybrid(construction, StubDetector([]))

    names = {canonical_class_name(d.class_name) for d in hybrid.detect(frame())}
    assert {"Person", "Mask", "Goggles", "Gloves"} <= names


def test_medical_profile_drops_construction_only_classes():
    construction = StubDetector(
        [
            det("Person", PERSON_BOX),
            det("Hardhat", (240, 30, 360, 90), 0.9),
            det("NO-Safety Vest", (210, 120, 400, 300), 0.7),
            det("Safety Boots", (220, 400, 300, 460), 0.65),
        ]
    )
    hybrid = make_hybrid(construction, StubDetector([]))

    names = {canonical_class_name(d.class_name) for d in hybrid.detect(frame())}
    assert names == {"Person"}
    # الشخص بس هو اللي عبر الجسر، والعدّاد الخام فاضل زي ما هو للمراقبة
    assert hybrid.last_stats.bridged == 1
    assert hybrid.last_stats.construction == 4


def test_no_bridge_when_construction_assist_disabled():
    construction = StubDetector([det("Person", PERSON_BOX)])
    medical = StubDetector([det("mask", (250, 60, 330, 130))])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
        run_construction_assist=False,
    )

    names = {canonical_class_name(d.class_name) for d in hybrid.detect(frame())}
    assert construction.calls == 0
    assert hybrid.last_stats.bridged == 0
    assert "Person" not in names


def test_construction_profile_keeps_construction_classes():
    construction = StubDetector(
        [
            det("Person", PERSON_BOX),
            det("Hardhat", (240, 30, 360, 90), 0.9),
        ]
    )
    hybrid = HybridPPEDetector(
        construction,
        None,
        primary_profile="construction",
        config=HybridConfig(skin_filter_enabled=False),
    )

    names = {canonical_class_name(d.class_name) for d in hybrid.detect(frame())}
    # في بروفايل الإنشاءات مفيش جسر — الفئات الإنشائية كلها تفضل
    assert {"Person", "Hardhat"} <= names
    assert hybrid.last_stats.bridged == 0


def test_bridged_person_enables_lab_coat_check():
    # الموديل الطبي معندوش Person — الشخص العابر من الجسر هو اللي بيوفر
    # "السياق الطبي" اللي بيخلي فحص غياب البالطو يشتغل
    construction = StubDetector([det("Person", PERSON_BOX, 0.85)])
    hybrid = make_hybrid(construction, StubDetector([]))
    detections = hybrid.detect(frame())

    checker = MedicalViolationChecker(cooldown_seconds=0, persist_seconds=0, grace_seconds=0.0)
    checker.check(7, detections, enabled_classes=["coat"])  # warm-up: يهيّئ حالة الكاميرا
    violations = checker.check(7, detections, enabled_classes=["coat"])

    assert {v.violation_type for v in violations} == {"no lab coat"}
