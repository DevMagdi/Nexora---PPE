from __future__ import annotations

import itertools
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from app.core.config import Settings, settings
from app.core.detector import Detection, PPEDetector, validate_class_names
from app.core.frame_annotator import annotate_frame
from app.core.postprocess import resolve_ppe_conflicts
from app.core.ppe import DANGER_BGR, GOLD_BGR, PPE_CLASSES, TEXT_BGR
from app.core.violation_checker import ViolationChecker


def det(name, confidence=0.9, box=(20, 10, 60, 40)):
    return Detection(0, name, confidence, *box)


def person(box=(0, 0, 100, 200)):
    return det("Person", box=box)


def test_one_person_hardhat_068_beats_no_hardhat_060_and_never_creates_violation(monkeypatch):
    """Required regression: the worn helmet cannot also become an alert."""
    raw = [person(), det("Hardhat", 0.68), det("NO-Hardhat", 0.60)]
    final = resolve_ppe_conflicts(raw)
    assert [d.class_name for d in final] == ["Person", "Hardhat"]
    assert final[1].confidence == 0.68 and final[1].person_index == 0
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker(persist_seconds=8)
    assert checker.check(1, raw, ["helmet"]) == []
    now[0] += 8
    assert checker.check(1, raw, ["helmet"]) == []
    now[0] += 60
    assert checker.check(1, final, ["helmet"]) == []


@pytest.mark.parametrize("key", list(PPE_CLASSES))
@pytest.mark.parametrize(
    ("positive", "negative", "negative_wins"),
    [
        (0.68, 0.60, False),
        (0.60, 0.60, False),
        (0.60, 0.67, False),
        (0.60, 0.68, False),
        (0.60, 0.74, False),
        (0.60, 0.75, True),
        (0.68, 0.83, True),
        (0.90, 0.80, False),
    ],
)
def test_all_five_rules_have_one_deterministic_conflict_winner(
    key, positive, negative, negative_wins
):
    pair = PPE_CLASSES[key]
    raw = [person(), det(pair["positive"], positive), det(pair["negative"], negative)]
    result = resolve_ppe_conflicts(raw)
    assert len(result) == 2
    assert result[1].class_name == pair["negative" if negative_wins else "positive"]
    assert result[1].color == (DANGER_BGR if negative_wins else GOLD_BGR)
    assert result[0].color == TEXT_BGR


def test_overlapping_regions_on_distinct_people_do_not_suppress_each_other():
    # Their PPE boxes overlap, but each has a different greatest Person IoU.
    raw = [
        person((0, 0, 100, 200)),
        person((80, 0, 180, 200)),
        det("Hardhat", 0.9, (65, 10, 95, 40)),
        det("NO-Hardhat", 0.8, (85, 10, 115, 40)),
    ]
    result = resolve_ppe_conflicts(raw)
    equipment = [d for d in result if d.class_name != "Person"]
    assert [d.person_index for d in equipment] == [0, 1]
    assert len(equipment) == 2


def test_nonintersecting_item_uses_nearest_person_center():
    result = resolve_ppe_conflicts(
        [
            person((0, 100, 100, 300)),
            person((200, 100, 300, 300)),
            det("Hardhat", box=(30, 65, 60, 90)),
        ]
    )
    assert result[-1].person_index == 0


def test_no_person_uses_local_overlap_without_fabricating_people_or_alert_classes():
    result = resolve_ppe_conflicts([det("Hardhat", 0.68), det("NO-Hardhat", 0.60)])
    assert len(result) == 1 and result[0].class_name == "Hardhat"
    assert result[0].person_index is None
    separate = resolve_ppe_conflicts(
        [det("Gloves", box=(0, 0, 10, 10)), det("NO-Gloves", box=(50, 0, 60, 10))]
    )
    assert len(separate) == 2  # Separate physical regions are not contradictory evidence.


def test_contained_ppe_conflicts_even_when_iou_of_the_small_box_is_low():
    result = resolve_ppe_conflicts(
        [person(), det("Hardhat", 0.8, (20, 10, 30, 20)), det("NO-Hardhat", 0.8, (0, 0, 80, 100))]
    )
    assert [d.class_name for d in result] == ["Person", "Hardhat"]


def test_conflict_components_and_order_are_stable_without_mutating_model_output():
    raw = [person(), det("Hardhat", 0.68), det("NO-Hardhat", 0.60), det("NO-Hardhat", 0.61)]
    for permutation in itertools.permutations(raw):
        resolved = resolve_ppe_conflicts(list(permutation))
        assert {d.class_name for d in resolved} == {"Person", "Hardhat"}
        assert len(resolved) == 2
        assert resolve_ppe_conflicts(resolved) == resolved
    assert all(d.person_index is None for d in raw)
    assert raw[0].color == GOLD_BGR  # Normalization copies, never edits raw objects.


@pytest.mark.parametrize("name", ["Mask", "Ladder", "Safety Cone", "Excavator"])
def test_nonindustrial_checkpoint_classes_are_ignored_without_stopping(name):
    canonical = validate_class_names(["person", "helmet", "no_helmet", "vest", name])
    assert set(canonical.values()) == {"Person", "Hardhat", "NO-Hardhat", "Safety Vest"}
    assert resolve_ppe_conflicts([det(name)]) == []


def test_boot_aliases_are_canonicalized_and_resolved():
    result = resolve_ppe_conflicts([person(), det("Boots", 0.68), det("NO-Boots", 0.60)])
    assert [d.class_name for d in result] == ["Person", "Safety Boots"]


def test_missing_negative_vest_only_disables_negative_alert_not_positive_detection(monkeypatch):
    detector = PPEDetector.__new__(PPEDetector)
    detector.class_names = validate_class_names(["person", "helmet", "no_helmet", "vest"])
    assert detector.supported_negative_rules == frozenset({"helmet"})
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker(persist_seconds=8)
    for t in [100.0, 108.0, 200.0]:
        now[0] = t
        assert (
            checker.check(1, [det("NO-Safety Vest")], ["vest"], detector.supported_negative_rules)
            == []
        )
    assert resolve_ppe_conflicts([det("Safety Vest")])[0].class_name == "Safety Vest"


@pytest.mark.parametrize("confidence", [0.40, 0.50, 0.55, 0.59])
def test_weak_negative_below_sixty_is_neither_displayed_nor_alerted(monkeypatch, confidence):
    """A negative must reach DETECTION_NEGATIVE_CONFIDENCE (0.60) to be shown."""
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    monkeypatch.setattr(settings, "DETECTION_NEGATIVE_CONFIDENCE", 0.60)
    raw = [det("NO-Hardhat", confidence)]
    assert resolve_ppe_conflicts(raw) == []
    checker = ViolationChecker(persist_seconds=8)
    assert checker.check(1, raw) == []
    now[0] += 8
    assert checker.check(1, raw) == []


def test_negative_at_sixty_is_displayed_and_alerted(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    monkeypatch.setattr(settings, "DETECTION_NEGATIVE_CONFIDENCE", 0.60)
    raw = [det("NO-Hardhat", 0.60)]
    displayed = resolve_ppe_conflicts(raw)
    assert [d.class_name for d in displayed] == ["NO-Hardhat"]
    assert displayed[0].color == DANGER_BGR
    checker = ViolationChecker(persist_seconds=8)
    assert checker.check(1, raw) == []
    now[0] = 108.0
    assert len(checker.check(1, raw)) == 1


def test_positive_equipment_still_displays_below_the_negative_floor(monkeypatch):
    monkeypatch.setattr(settings, "DETECTION_NEGATIVE_CONFIDENCE", 0.60)
    result = resolve_ppe_conflicts([det("Hardhat", 0.52)])
    assert [d.class_name for d in result] == ["Hardhat"]


def test_negative_floor_can_never_drop_below_sixty(monkeypatch):
    monkeypatch.setattr(settings, "DETECTION_NEGATIVE_CONFIDENCE", 0.60)
    result = resolve_ppe_conflicts([det("NO-Hardhat", 0.60)], display_confidence=0.45)
    assert len(result) == 1


def test_weak_conflict_resets_persistence(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker(persist_seconds=8)
    raw = [det("NO-Hardhat", 0.62)]
    assert checker.check(1, raw) == []
    now[0] = 108.0
    assert len(checker.check(1, raw)) == 1
    checker.reset(1)
    now[0] = 200.0
    checker.check(1, [det("NO-Hardhat", 0.9)])
    now[0] = 207.0
    checker.check(1, [det("Hardhat", 0.91), det("NO-Hardhat", 0.9)])
    now[0] = 208.0
    assert checker.check(1, [det("NO-Hardhat", 0.9)]) == []


@pytest.mark.parametrize("value", [0.30, 0.50, 0.55, 0.59])
def test_negative_confidence_below_sixty_is_rejected(value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, DETECTION_NEGATIVE_CONFIDENCE=value)


def test_negative_confidence_accepts_sixty_and_above():
    for value in (0.60, 0.75, 1.0):
        assert Settings(
            _env_file=None, DETECTION_NEGATIVE_CONFIDENCE=value
        ).DETECTION_NEGATIVE_CONFIDENCE == pytest.approx(value)


def test_annotation_cannot_draw_both_conflicting_labels_even_if_given_raw_boxes(monkeypatch):
    labels = []

    def draw(_frame, text, _position, **_kwargs):
        labels.append(text)

    monkeypatch.setattr("app.core.frame_annotator.draw_text_with_background", draw)
    raw = [person(), det("Hardhat", 0.68), det("NO-Hardhat", 0.60)]
    annotate_frame(np.zeros((200, 100, 3), np.uint8), raw, [])
    assert len(labels) == 2 and labels[1].startswith("Hardhat")
    assert not any("NO-Hardhat" in label for label in labels)


def test_actual_detector_runs_postprocess_before_returning():
    detector = PPEDetector.__new__(PPEDetector)
    detector._lock = threading.Lock()
    detector.confidence = 0.50
    detector.class_names = {0: "Person", 1: "Hardhat", 2: "NO-Hardhat"}
    boxes = [
        SimpleNamespace(cls=[i], conf=[confidence], xyxy=[coords])
        for i, confidence, coords in [
            (0, 0.9, [0, 0, 100, 200]),
            (1, 0.68, [20, 10, 60, 40]),
            (2, 0.60, [20, 10, 60, 40]),
        ]
    ]
    detector.model = lambda *_args, **_kwargs: [SimpleNamespace(boxes=boxes)]
    assert [d.class_name for d in detector.detect(np.zeros((200, 100, 3), np.uint8))] == [
        "Person",
        "Hardhat",
    ]
