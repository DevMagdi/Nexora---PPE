"""
اختبارات مزامنة العرض مع القواعد (rule-synced display).

بث الكاميرا والأسطر الإحصائية لازم يعكسوا نفس الفئات اللي الكاميرا بتفحصها
بالفعل: ``Person`` دايمًا (للسياق) + الفئات الموجبة/السالبة للمفاتيح المفعّلة
— بما فيها الكشوف المولّدة من فلتر الجلد. أي فئة مش مفعّلة متظهرش حتى لو
الموديل كشفها.
"""

from __future__ import annotations

from app.camera.manager import CameraManager
from app.core.detector import Detection


def det(
    class_name: str,
    box: tuple[int, int, int, int] = (0, 0, 10, 10),
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


def test_construction_display_syncs_with_enabled_rules():
    manager = CameraManager({})
    detections = [
        det("Person"),
        det("Hardhat"),
        det("NO-Hardhat"),
        det("Safety Vest"),  # الفيست مش مفعّل على الكاميرا دي
        det("NO-Mask"),
        det("NO-Goggles", source="skin:eye_bridge"),  # كشف جلد لفئة مش مفعّلة
    ]

    displayed = manager._filter_detections_for_display(
        "construction", ["helmet", "mask"], detections
    )
    names = sorted(d.class_name for d in displayed)

    assert names == ["Hardhat", "NO-Hardhat", "NO-Mask", "Person"]


def test_medical_display_syncs_and_empty_rules_keep_only_person():
    manager = CameraManager({})
    detections = [
        det("Person"),
        det("Mask"),
        det("NO-Mask"),
        det("Head Cap"),
        det("NO-Head Cap"),
        det("Gloves"),  # الجوانتي مش مفعّل
        det("NO-Goggles", source="skin:eye_bridge"),  # النظارة مش مفعّلة
    ]

    displayed = manager._filter_detections_for_display(
        "medical", ["mask", "cap"], detections
    )
    assert {d.class_name for d in displayed} == {
        "Person",
        "Mask",
        "NO-Mask",
        "Head Cap",
        "NO-Head Cap",
    }

    # من غير أي قواعد مفعّلة: الشخص بس هو اللي يظهر (سياق)
    only_person = manager._filter_detections_for_display("medical", [], detections)
    assert [d.class_name for d in only_person] == ["Person"]
