"""
اختبارات الجسر التشريحي (anatomical eye bridge).

كاميرات القطاع الطبي ممكن تشتغل من غير فئة ``Person`` (الموديل الطبي معندوش
الفئة، والمساعد الإنشائي ممكن يكون مقفول). الجسر التشريحي بيستخدم كل كشف
``Mask`` كمرجع تشريحي: خط العينين/جسر الأنف بيكون مباشرة فوق الكمامة، فلو
الشريط ده جلد مكشوف ⇒ ``NO-Goggles``.
"""

from __future__ import annotations

import numpy as np

from app.core.detector import Detection
from app.core.hybrid_detector import (
    SOURCE_ANATOMICAL_BRIDGE,
    SOURCE_EYE_BRIDGE,
    HybridConfig,
    HybridPPEDetector,
)
from app.core.ppe import canonical_class_name

SKIN_BGR = (150, 175, 220)
DARK_BGR = (10, 10, 10)
BG_BGR = (90, 90, 90)

# بوكس الكمامة اللي هيبني عليه الجسر التشريحي منطقة خط العينين
MASK_BOX = (250, 150, 390, 230)
# منطقة خط العينين المستنتجة: أعرض من الكمامة بشوية وممتدة فوق حافتها
EYE_ZONE = (229, 82, 411, 170)
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


def face_over_mask_frame() -> np.ndarray:
    """فريم فيه وش بجلد مكشوف وعينين داكنتين فوق الكمامة مباشرة (من غير شخص)."""
    frame = np.full((480, 640, 3), BG_BGR, dtype=np.uint8)

    zx1, zy1, zx2, zy2 = EYE_ZONE
    # وش (جلد) يغطي منطقة خط العينين وهامشها
    frame[zy1 - 8 : zy2 + 8, zx1 - 15 : zx2 + 15] = SKIN_BGR

    # عينين داكنتين على خط العينين
    eye_y = zy1 + int((zy2 - zy1) * 0.42)
    eye_h = max(4, (zy2 - zy1) // 9)
    eye_w = max(4, (zx2 - zx1) // 9)
    for ratio in (0.22, 0.78):
        ex = zx1 + int((zx2 - zx1) * ratio)
        frame[eye_y : eye_y + eye_h, ex : ex + eye_w] = DARK_BGR

    return frame


def test_anatomical_eye_bridge_without_person():
    medical = StubDetector([det("mask", MASK_BOX, 0.8)])
    hybrid = HybridPPEDetector(None, medical, primary_profile="medical")

    detections = hybrid.detect(face_over_mask_frame())
    no_goggles = [d for d in detections if canonical_class_name(d.class_name) == "NO-Goggles"]

    assert len(no_goggles) == 1
    assert no_goggles[0].source == SOURCE_ANATOMICAL_BRIDGE
    assert no_goggles[0].confidence >= 0.45
    assert hybrid.last_stats.eye_bridge_hits == 1


def test_anatomical_eye_bridge_skipped_when_person_exists():
    # مع وجود Person الفحص الأصلي (من مستطيل الرأس) هو اللي بيشتغل —
    # الجسر التشريحي احتياطي لحالة غياب الشخص فقط
    construction = StubDetector([det("Person", PERSON_BOX)])
    medical = StubDetector([det("mask", MASK_BOX, 0.8)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        run_construction_assist=True,
    )

    detections = hybrid.detect(face_over_mask_frame())
    sources = [getattr(d, "source", "") for d in detections]

    assert SOURCE_ANATOMICAL_BRIDGE not in sources
    assert any(s == SOURCE_EYE_BRIDGE for s in sources)


def test_anatomical_eye_bridge_respects_disabled_flag():
    medical = StubDetector([det("mask", MASK_BOX, 0.8)])
    hybrid = HybridPPEDetector(
        None,
        medical,
        primary_profile="medical",
        config=HybridConfig(eye_bridge_enabled=False),
    )

    names = {canonical_class_name(d.class_name) for d in hybrid.detect(face_over_mask_frame())}
    assert names == {"Mask"}


def test_anatomical_eye_bridge_downgrades_weak_goggles():
    medical = StubDetector(
        [
            det("mask", MASK_BOX, 0.8),
            det("goggle", (240, 90, 400, 160), 0.5),  # كشف نظارة ضعيف على منطقة مكشوفة
        ]
    )
    hybrid = HybridPPEDetector(None, medical, primary_profile="medical")

    names = {canonical_class_name(d.class_name) for d in hybrid.detect(face_over_mask_frame())}
    assert "NO-Goggles" in names
    assert "Goggles" not in names
