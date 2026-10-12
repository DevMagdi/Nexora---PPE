"""
اختبارات نسبة رفض القفاز (glove reject ratio = 24%).

بوكس ``Gloves`` اللي جواه ≥24% جلد مكشوف سميكة (distanceTransform) هو قفاز
وهمي ⇒ بيتقلب ``NO-Gloves``. القفاز الحقيقي مبيبانوش جلد في نصه، فالعتبة
الجديدة (0.24) أصرم من ``SKIN_STRONG_RATIO`` (0.32) القديمة ومظبوطة على
حالة "قفاز الموديل الغلط على يد عارية".
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.config import Settings
from app.core.detector import Detection
from app.core.hybrid_detector import HybridConfig, HybridPPEDetector
from app.core.ppe import canonical_class_name

SKIN_BGR = (150, 175, 220)
BLUE_GLOVE_BGR = (230, 120, 60)
BG_BGR = (90, 90, 90)

PERSON_BOX = (200, 40, 420, 460)
GLOVE_BOX = (200, 250, 300, 450)
# رقعة جلد ~27% من مساحة بوكس القفاز (بين عتبة 24% الجديدة و32% القديمة)
SKIN_PATCH = (slice(280, 367), slice(210, 297))


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


def frame_with_partially_bare_glove_box() -> np.ndarray:
    """بوكس قفاز من الموديل تحته يد عارية جزئيًا (~27% جلد مكشوف)."""
    frame = np.full((480, 640, 3), BG_BGR, dtype=np.uint8)
    gx1, gy1, gx2, gy2 = GLOVE_BOX
    frame[gy1:gy2, gx1:gx2] = BLUE_GLOVE_BGR
    frame[SKIN_PATCH] = SKIN_BGR
    return frame


def make_hybrid(config: HybridConfig | None = None) -> HybridPPEDetector:
    construction = StubDetector([det("Person", PERSON_BOX)])
    medical = StubDetector([det("hand gloves", GLOVE_BOX, 0.55)])
    return HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=config,
        run_construction_assist=True,
    )


def test_glove_reject_ratio_default_is_24_percent():
    assert Settings(_env_file=None).SKIN_GLOVE_REJECT_RATIO == pytest.approx(0.24)
    assert HybridConfig().glove_reject_ratio == pytest.approx(0.24)
    assert HybridConfig.from_settings().glove_reject_ratio == pytest.approx(0.24)


def test_glove_rejected_between_24_and_32_percent_skin():
    frame = frame_with_partially_bare_glove_box()

    # العتبة الافتراضية 24% ⇒ جلد ~27% كفاية لرفض القفاز
    strict_names = {
        canonical_class_name(d.class_name) for d in make_hybrid().detect(frame)
    }
    assert "Gloves" not in strict_names
    assert "NO-Gloves" in strict_names

    # عتبة أرحب (35%) ⇒ نفس الفريم مايرفضش القفاز — العتبة هي اللي بتحكم
    lenient_names = {
        canonical_class_name(d.class_name)
        for d in make_hybrid(HybridConfig(glove_reject_ratio=0.35)).detect(frame)
    }
    assert "Gloves" in lenient_names
