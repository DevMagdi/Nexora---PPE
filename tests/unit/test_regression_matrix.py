"""Large, deterministic regression matrix for cross-model PPE label handling.

The construction and medical checkpoints use different capitalization and word
separators for overlapping classes. Every parameter below is an independently
collected pytest case, not a loop hidden inside a single test.
"""

from __future__ import annotations

from itertools import product

import pytest

from app.core.ppe import (
    CANONICAL_CLASS_NAMES,
    CLASS_NAME_ALIASES,
    canonical_class_name,
    class_key,
    is_negative_class,
)


def _build_alias_variants() -> list[tuple[str, str]]:
    """Enumerate case and separator spellings for every alias and canonical label."""
    expected_by_candidate: dict[str, str] = {}
    class_pairs = [
        *CLASS_NAME_ALIASES.items(),
        *((name, name) for name in CANONICAL_CLASS_NAMES),
    ]

    for alias, canonical in class_pairs:
        words = alias.split()
        separators = product((" ", "_", "-"), repeat=max(0, len(words) - 1))
        for choices in separators:
            rendered = words[0] if words else ""
            for separator, word in zip(choices, words[1:], strict=True):
                rendered += separator + word
            for candidate in {rendered, rendered.lower(), rendered.upper()}:
                previous = expected_by_candidate.setdefault(candidate, canonical)
                if previous != canonical:
                    raise AssertionError(
                        f"Ambiguous class-label test case {candidate!r}: "
                        f"{previous!r} vs {canonical!r}"
                    )

    return sorted(expected_by_candidate.items())


_ALIAS_VARIANTS = _build_alias_variants()
_NEGATIVE_CLASS_CASES = [
    (alias, canonical.startswith("NO-")) for alias, canonical in CLASS_NAME_ALIASES.items()
] + [(name, name.startswith("NO-")) for name in CANONICAL_CLASS_NAMES]
_CLASS_KEY_EDGE_CASES = [
    ("  NO   MASK  ", "no mask"),
    ("No_Mask", "no mask"),
    ("No-Mask", "no mask"),
    ("No\tMask", "no mask"),
    ("Hardhat", "hardhat"),
    ("    ", ""),
    ("NO---MASK", "no mask"),
    ("Safety_Vest", "safety vest"),
]


@pytest.mark.parametrize(
    ("candidate", "expected"),
    _ALIAS_VARIANTS,
    ids=[f"{candidate!r}-to-{expected}" for candidate, expected in _ALIAS_VARIANTS],
)
def test_all_model_alias_spellings_resolve_to_one_canonical_class(candidate: str, expected: str):
    assert canonical_class_name(candidate) == expected


@pytest.mark.parametrize(
    ("alias", "expected_negative"),
    _NEGATIVE_CLASS_CASES,
    ids=[f"{alias!r}-negative={expected}" for alias, expected in _NEGATIVE_CLASS_CASES],
)
def test_every_model_alias_preserves_positive_or_negative_polarity(
    alias: str, expected_negative: bool
):
    assert is_negative_class(alias) is expected_negative


@pytest.mark.parametrize(
    ("candidate", "expected"),
    _CLASS_KEY_EDGE_CASES,
    ids=[f"{candidate!r}-key={expected!r}" for candidate, expected in _CLASS_KEY_EDGE_CASES],
)
def test_class_keys_collapse_supported_separator_and_whitespace_variants(
    candidate: str, expected: str
):
    assert class_key(candidate) == expected
