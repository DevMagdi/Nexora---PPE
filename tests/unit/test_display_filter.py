from __future__ import annotations

import pytest

from app.camera.manager import CameraManager
from app.core.detector import Detection
from app.core.ppe import CANONICAL_CLASS_NAMES, sanitize_enabled_classes


def _detections():
    return [
        Detection(index, name, 0.9, 1, 1, 10, 10)
        for index, name in enumerate(CANONICAL_CLASS_NAMES)
    ]


def test_display_uses_only_enabled_rules_and_person_context():
    detections = _detections()
    result = CameraManager._filter_detections_for_display(["helmet", "boots"], detections)
    assert {d.class_name for d in result} == {
        "Person",
        "Hardhat",
        "NO-Hardhat",
        "Safety Boots",
        "NO-Boot",
    }


def test_counts_cover_all_and_only_industrial_classes():
    counts = CameraManager._compute_counts(_detections())
    assert counts["total"] == len(CANONICAL_CLASS_NAMES)
    assert counts["person"] == 1
    assert (
        counts["no_hardhat"] == counts["no_vest"] == counts["no_boot"] == counts["no_goggles"] == 1
    )
    assert len(counts) == len(CANONICAL_CLASS_NAMES) + 1


@pytest.mark.parametrize("value", [["unknown"], ["helmet", "unknown"], [], "helmet", [None]])
def test_out_of_scope_rules_are_rejected_not_silently_enabled(value):
    with pytest.raises(ValueError):
        sanitize_enabled_classes(value)


def test_default_and_deduplicated_rules():
    assert sanitize_enabled_classes(None) == ["helmet", "vest"]
    assert sanitize_enabled_classes(["helmet", "helmet"]) == ["helmet"]
