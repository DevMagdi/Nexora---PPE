from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np
import pytest

from app.core.detector import DANGER_BGR, GOLD_BGR, PPEDetector
from app.core.ppe import CANONICAL_CLASS_NAMES


def _box(class_id, confidence, coords):
    return SimpleNamespace(cls=[class_id], conf=[confidence], xyxy=[coords])


def _detector(boxes):
    detector = PPEDetector.__new__(PPEDetector)
    detector._lock = threading.Lock()
    detector.confidence = 0.50
    detector.class_names = dict(enumerate(CANONICAL_CLASS_NAMES))
    detector.model = lambda *_args, **_kwargs: [SimpleNamespace(boxes=boxes)]
    return detector


def test_boxes_are_clipped_and_colored_from_identity():
    detector = _detector([_box(1, 0.9, [-10, -5, 1000, 1000]), _box(2, 0.9, [1, 2, 30, 40])])
    result = detector.detect(np.zeros((64, 80, 3), dtype=np.uint8))
    assert (result[0].x1, result[0].y1, result[0].x2, result[0].y2) == (0, 0, 80, 64)
    assert result[0].color == GOLD_BGR
    assert result[1].color == DANGER_BGR


@pytest.mark.parametrize(
    "box",
    [
        _box(100, 0.9, [1, 1, 10, 10]),
        _box(2, 0.49, [1, 1, 10, 10]),
        _box(2, float("nan"), [1, 1, 10, 10]),
        _box(2, 1.1, [1, 1, 10, 10]),
        _box(2, 0.9, [10, 10, 1, 1]),
        _box(2, 0.9, [0, 0, float("inf"), 1]),
        _box(2, 0.9, [0, 0, 0, 1]),
    ],
)
def test_unsafe_boxes_never_escape_detector(box):
    assert _detector([box]).detect(np.zeros((64, 64, 3), dtype=np.uint8)) == []


@pytest.mark.parametrize(
    "frame", [None, np.zeros((0, 0, 3)), np.zeros((12, 12)), np.zeros((12, 12, 4))]
)
def test_invalid_input_is_rejected(frame):
    with pytest.raises(ValueError, match="BGR"):
        _detector([]).detect(frame)
