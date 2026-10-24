from __future__ import annotations

import pytest

from app.core.detector import Detection
from app.core.violation_checker import ViolationChecker, apply_persist_floor


def detection(name="NO-Hardhat", confidence=0.9, source="model"):
    return Detection(0, name, confidence, 1, 1, 20, 20, source=source)


def test_floor_prevents_short_legacy_persistence():
    assert apply_persist_floor(3, 8) == 8
    assert apply_persist_floor(12, 8) == 12


@pytest.mark.parametrize(
    ("key", "negative"),
    [
        ("helmet", "NO-Hardhat"),
        ("vest", "NO-Safety Vest"),
        ("gloves", "NO-Gloves"),
        ("boots", "NO-Boot"),
        ("goggles", "NO-Goggles"),
    ],
)
def test_every_industrial_rule_requires_sustained_model_evidence(monkeypatch, key, negative):
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker(cooldown_seconds=60, persist_seconds=8)
    assert checker.check(1, [detection(negative)], [key]) == []
    now[0] += 7.9
    assert checker.check(1, [detection(negative)], [key]) == []
    now[0] += 0.1
    events = checker.check(1, [detection(negative)], [key])
    assert len(events) == 1
    assert events[0].violation_type == negative
    assert events[0].confidence == 0.9
    now[0] += 10
    assert checker.check(1, [detection(negative)], [key]) == []


def test_clean_frame_resets_persistence_but_keeps_cooldown(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker(persist_seconds=8)
    checker.check(1, [detection()])
    now[0] = 107
    checker.check(1, [])
    now[0] = 108
    assert checker.check(1, [detection()]) == []
    now[0] = 116
    assert len(checker.check(1, [detection()])) == 1
    now[0] = 117
    checker.check(1, [])
    now[0] = 118
    checker.check(1, [detection()])
    now[0] = 126
    assert checker.check(1, [detection()]) == []


def test_gap_in_telemetry_cannot_accumulate_persistence(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker()
    checker.check(1, [detection()])
    now[0] += 20
    assert checker.check(1, [detection()]) == []


def test_absent_equipment_or_unknown_source_never_synthesizes_violation(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker()
    checker.check(1, [detection("Person")])
    now[0] += 8
    assert checker.check(1, [detection("Person"), detection(source="heuristic")]) == []
    assert checker.check(2, [detection(confidence=0.2)]) == []


def test_disabled_rules_and_other_cameras_do_not_trigger(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.core.violation_checker.time.monotonic", lambda: now[0])
    checker = ViolationChecker()
    checker.check(1, [detection()], ["helmet"])
    now[0] += 8
    assert checker.check(2, [detection()], ["helmet"]) == []
    assert checker.check(1, [detection()], ["vest"]) == []
    checker.reset(1)
    assert checker.check(1, [detection()], ["helmet"]) == []
