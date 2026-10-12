from __future__ import annotations

import numpy as np
import pytest

from app.core.skin_analysis import (
    analyze_skin_region,
    calc_skin_ratio,
    eye_bridge_exposed,
    hand_candidate_boxes,
    head_box,
    lower_face_box,
    ratio_confidence,
    skin_region_mask,
)

SKIN_BGR = (150, 175, 220)  # لون جلد (BGR) داخل نطاق HSV/YCrCb
DARK_BGR = (12, 12, 12)
WHITE_BGR = (245, 245, 245)
BLUE_GLOVE_BGR = (230, 120, 60)


def solid(bgr: tuple[int, int, int], h: int = 64, w: int = 64) -> np.ndarray:
    return np.full((h, w, 3), bgr, dtype=np.uint8)


def skin_with_dark_eyes(h: int = 96, w: int = 96) -> np.ndarray:
    """وش بجلد واضح + عينين داكنتين (بدون نظارة)."""
    face = solid(SKIN_BGR, h, w)
    eye_y = int(h * 0.42)
    eye_h, eye_w = max(4, h // 9), max(4, w // 9)
    for x_ratio in (0.22, 0.78):
        x = int(w * x_ratio)
        face[eye_y : eye_y + eye_h, x : x + eye_w] = DARK_BGR
    return face


def skin_with_goggles(h: int = 96, w: int = 96) -> np.ndarray:
    """وش + نظارة واقية: شريط زجاجي عاكس (فاتح/منخفض التشبع) على خط العينين."""
    face = solid(SKIN_BGR, h, w)
    top = int(h * 0.32)
    bottom = int(h * 0.58)
    face[top:bottom, int(w * 0.10) : int(w * 0.90)] = (250, 250, 250)
    # إطار غامق
    face[top : top + 2, int(w * 0.10) : int(w * 0.90)] = (40, 40, 40)
    face[bottom - 2 : bottom, int(w * 0.10) : int(w * 0.90)] = (40, 40, 40)
    return face


# ---------------------------------------------------------------------------
# calc_skin_ratio / mask
# ---------------------------------------------------------------------------


def test_skin_mask_flags_skin_only():
    mask = skin_region_mask(solid(SKIN_BGR))
    assert mask.shape[:2] == (64, 64)
    assert float(np.count_nonzero(mask)) / mask.size > 0.95


def test_skin_mask_rejects_white_and_blue_glove():
    assert calc_skin_ratio(solid(WHITE_BGR)) < 0.05
    assert calc_skin_ratio(solid(BLUE_GLOVE_BGR)) < 0.05
    assert calc_skin_ratio(solid(DARK_BGR)) < 0.05


def test_calc_skin_ratio_is_bounded_and_handles_empty():
    assert calc_skin_ratio(np.zeros((0, 0, 3), dtype=np.uint8)) == 0.0
    ratio = calc_skin_ratio(solid(SKIN_BGR))
    assert 0.0 <= ratio <= 1.0


def test_calc_skin_ratio_partial_coverage():
    img = solid(SKIN_BGR, 40, 40)
    img[:, :20] = WHITE_BGR
    ratio = calc_skin_ratio(img)
    assert 0.35 <= ratio <= 0.65


# ---------------------------------------------------------------------------
# distanceTransform bare-hand detector
# ---------------------------------------------------------------------------


def test_bare_hand_detected_on_thick_skin_blob():
    stats = analyze_skin_region(solid(SKIN_BGR, 80, 80))
    assert stats.is_bare is True
    assert stats.thickness > 0.3
    assert stats.confidence > 0.8


def test_gloved_hand_not_bare():
    stats = analyze_skin_region(solid(BLUE_GLOVE_BGR, 80, 80))
    assert stats.is_bare is False
    assert stats.skin_ratio < 0.05
    assert stats.thickness == pytest.approx(0.0)


def test_thin_skin_stripes_are_not_a_hand():
    """شرائط جلد رقيقة (ذراع/خلفية) لازم ما تتفسّرش كيد عارية."""
    img = solid(WHITE_BGR, 80, 80)
    for x in range(0, 80, 8):
        img[:, x : x + 2] = SKIN_BGR
    stats = analyze_skin_region(img)
    assert stats.skin_ratio > 0.0
    assert stats.is_bare is False
    assert stats.thickness < 0.12


def test_analyze_skin_region_tolerates_degenerate_input():
    empty = analyze_skin_region(np.zeros((0, 0, 3), dtype=np.uint8))
    assert empty.is_valid is False
    assert empty.is_bare is False


def test_ratio_confidence_bounds():
    assert ratio_confidence(0.0, 0.2, 0.5) == 0.0
    assert ratio_confidence(0.9, 0.2, 0.5) == 1.0
    assert ratio_confidence(0.35, 0.2, 0.5) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# eye bridge (NO-Goggles)
# ---------------------------------------------------------------------------


def test_eye_bridge_exposed_on_bare_face():
    result = eye_bridge_exposed(skin_with_dark_eyes())
    assert result.exposed is True
    assert result.skin_ratio > 0.2
    assert result.confidence > 0.4
    assert result.bridge_box is not None


def test_eye_bridge_not_exposed_with_goggles():
    result = eye_bridge_exposed(skin_with_goggles())
    assert result.exposed is False
    assert result.confidence == pytest.approx(0.0)


def test_eye_bridge_needs_usable_face_region():
    result = eye_bridge_exposed(np.zeros((10, 10, 3), dtype=np.uint8))
    assert result.exposed is False
    assert result.confidence == 0.0


def test_eye_bridge_detects_dark_eye_candidates():
    from app.core.skin_analysis import _dark_eye_candidates

    candidates = _dark_eye_candidates(skin_with_dark_eyes())
    assert len(candidates) >= 2


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def test_head_and_lower_face_geometry():
    person = (100, 200, 200, 600)
    head = head_box(person, 0.32)
    assert head == (100, 200, 200, 200 + int(400 * 0.32))

    lower = lower_face_box(head, top=0.45)
    assert lower[1] > head[1]
    assert lower[3] == head[3]
    assert lower[0] > head[0] and lower[2] < head[2]


def test_hand_candidate_boxes_inside_person():
    person = (0, 0, 100, 400)
    boxes = hand_candidate_boxes(person)
    assert len(boxes) >= 3
    for x1, y1, x2, y2 in boxes:
        assert x1 >= person[0] and x2 <= person[2]
        assert y1 >= person[1] and y2 <= person[3]
        assert x2 > x1 and y2 > y1
