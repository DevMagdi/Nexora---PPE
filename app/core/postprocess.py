"""One deterministic PPE decision layer shared by inference, previews and alerts.

Person indices are frame-local associations, NOT tracking identities. Conflicts
are spatially overlapping positive/negative evidence for the same person/rule.
No person or negative equipment class is ever fabricated.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import replace
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.ppe import DANGER_BGR, GOLD_BGR, PPE_CLASSES, TEXT_BGR, canonical_class_name

if TYPE_CHECKING:
    from app.core.detector import Detection

# Near ties (< .08) prefer positive. The uncertainty band up to .15 also
# remains positive: an explicit negative must win by a clear >= .15 margin.
NEAR_TIE_MARGIN = 0.08
NEGATIVE_CLEAR_MARGIN = 0.15
_EPS = 1e-9
_RULE_FOR_CLASS = {
    name: (key, sign)
    for key, pair in PPE_CLASSES.items()
    for sign, name in (("positive", pair["positive"]), ("negative", pair["negative"]))
}


def _area(d: Detection) -> float:
    return (d.x2 - d.x1) * (d.y2 - d.y1)


def _intersection(a: Detection, b: Detection) -> float:
    return max(0, min(a.x2, b.x2) - max(a.x1, b.x1)) * max(0, min(a.y2, b.y2) - max(a.y1, b.y1))


def _iou(a: Detection, b: Detection) -> float:
    intersection = _intersection(a, b)
    return intersection / (_area(a) + _area(b) - intersection)


def _distance_squared(a: Detection, b: Detection) -> float:
    return ((a.x1 + a.x2 - b.x1 - b.x2) / 2) ** 2 + ((a.y1 + a.y2 - b.y1 - b.y2) / 2) ** 2


def _same_region(a: Detection, b: Detection) -> bool:
    intersection = _intersection(a, b)
    return intersection > 0 and (
        _iou(a, b) >= 0.10 or intersection / min(_area(a), _area(b)) >= 0.50
    )


def _winner(indices: list[int], detections: list[Detection]) -> int:
    def rank(index: int):
        d = detections[index]
        return d.confidence, -d.x1, -d.y1, -d.x2, -d.y2, -d.class_id

    positives = [i for i in indices if not detections[i].class_name.startswith("NO-")]
    negatives = [i for i in indices if detections[i].class_name.startswith("NO-")]
    positive, negative = max(positives, key=rank), max(negatives, key=rank)
    difference = detections[negative].confidence - detections[positive].confidence
    if abs(difference) < NEAR_TIE_MARGIN - _EPS:
        return positive
    return negative if difference + _EPS >= NEGATIVE_CLEAR_MARGIN else positive


def negative_threshold(display_confidence: float | None = None) -> float:
    """Explicit negative evidence must clear DETECTION_NEGATIVE_CONFIDENCE (>= .60)."""
    display = settings.DETECTION_CONFIDENCE if display_confidence is None else display_confidence
    return max(display, settings.DETECTION_NEGATIVE_CONFIDENCE)


def resolve_ppe_conflicts(
    detections: list[Detection], *, display_confidence: float | None = None
) -> list[Detection]:
    """Canonicalize, associate, and keep exactly one winner per conflict region.

    Use greatest Person IoU, then nearest center; if there is no Person, resolve
    only overlapping PPE regions without inventing an owner. Non-overlapping
    equipment and different people never suppress each other's evidence.
    """
    threshold = settings.DETECTION_CONFIDENCE if display_confidence is None else display_confidence
    # Negative evidence is only displayed/alerts at the explicit-negative floor;
    # the display threshold alone never paints a weak NO-* box.
    negatives_threshold = negative_threshold(threshold)
    normalized: list[Detection] = []
    for d in detections:
        name = canonical_class_name(d.class_name)
        floor = negatives_threshold if name.startswith("NO-") else threshold
        if (
            not name
            or d.source != "model"
            or not math.isfinite(d.confidence)
            or not floor <= d.confidence <= 1.0
            or not all(math.isfinite(value) for value in (d.x1, d.y1, d.x2, d.y2))
            or d.x2 <= d.x1
            or d.y2 <= d.y1
        ):
            continue
        color = TEXT_BGR if name == "Person" else DANGER_BGR if name.startswith("NO-") else GOLD_BGR
        normalized.append(replace(d, class_name=name, color=color, person_index=None))
    people = [d for d in normalized if d.class_name == "Person"]
    for index, person in enumerate(people):
        person.person_index = index
    buckets: dict[tuple[int | None, str], list[int]] = defaultdict(list)
    for index, d in enumerate(normalized):
        if d.class_name == "Person":
            continue
        if people:
            owner = max(
                range(len(people)),
                key=lambda i: (
                    _iou(d, people[i]),
                    -_distance_squared(d, people[i]),
                    people[i].confidence,
                    -i,
                ),
            )
            d.person_index = owner
        buckets[(d.person_index, _RULE_FOR_CLASS[d.class_name][0])].append(index)
    suppressed: set[int] = set()
    for indices in buckets.values():
        positive = [i for i in indices if not normalized[i].class_name.startswith("NO-")]
        negative = [i for i in indices if normalized[i].class_name.startswith("NO-")]
        if not positive or not negative:
            continue
        parents = {i: i for i in indices}

        def root(i, parents=parents):
            while parents[i] != i:
                parents[i] = parents[parents[i]]
                i = parents[i]
            return i

        for p in positive:
            for n in negative:
                if _same_region(normalized[p], normalized[n]):
                    parents[root(n)] = root(p)
        components: dict[int, list[int]] = defaultdict(list)
        for i in indices:
            components[root(i)].append(i)
        for component in components.values():
            if len({normalized[i].class_name.startswith("NO-") for i in component}) != 2:
                continue
            chosen = _winner(component, normalized)
            suppressed.update(i for i in component if i != chosen)
    return [d for i, d in enumerate(normalized) if i not in suppressed]
