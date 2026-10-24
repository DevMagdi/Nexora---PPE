from __future__ import annotations

import pytest

from app.core.ppe import CANONICAL_CLASS_NAMES, PPE_CLASSES, canonical_class_name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("hard_hat", "Hardhat"),
        ("NO-Helmet", "NO-Hardhat"),
        ("no_safety_vest", "NO-Safety Vest"),
        ("Safety Boot", "Safety Boots"),
        ("NO-Safety Boots", "NO-Boot"),
        ("NO-Boot", "NO-Boot"),
        ("no hand gloves", "NO-Gloves"),
        ("no_goggle", "NO-Goggles"),
        ("worker", "Person"),
        ("unapproved", ""),
    ],
)
def test_industrial_alias_matrix(name, expected):
    assert canonical_class_name(name) == expected


def test_all_rules_have_a_canonical_positive_and_negative():
    assert len(CANONICAL_CLASS_NAMES) == 11
    for rule in PPE_CLASSES.values():
        assert canonical_class_name(rule["positive"]) == rule["positive"]
        assert canonical_class_name(rule["negative"]) == rule["negative"]
        assert rule["negative"].startswith("NO-")
