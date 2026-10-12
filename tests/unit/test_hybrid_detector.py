from __future__ import annotations

import numpy as np

from app.core.detector import Detection
from app.core.hybrid_detector import (
    SOURCE_EYE_BRIDGE,
    SOURCE_HAND,
    SOURCE_MOUTH,
    HybridConfig,
    HybridPPEDetector,
    detection_box,
)
from app.core.ppe import canonical_class_name, class_key
from app.core.skin_analysis import hand_candidate_boxes, head_box, lower_face_box

SKIN_BGR = (150, 175, 220)
WHITE_BGR = (245, 245, 245)
BLUE_GLOVE_BGR = (230, 120, 60)


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
    """موديل وهمي بترجع كشوف ثابتة (بدون torch/ultralytics)."""

    def __init__(self, detections: list[Detection], names: dict[int, str] | None = None) -> None:
        self._detections = detections
        self.calls = 0
        self.names = names or {}
        self.class_names = names or {}

    def detect(self, frame: np.ndarray) -> list[Detection]:  # noqa: ARG002
        self.calls += 1
        return [det(d.class_name, detection_box(d), d.confidence, d.source) for d in self._detections]


def frame_with_person() -> np.ndarray:
    """فريم 640×480: شخص يمين + رأس بجلد وعينين داكنتين + مناطق يدين بجلد."""
    frame = np.full((480, 640, 3), (90, 90, 90), dtype=np.uint8)
    person = (200, 40, 420, 460)
    x1, y1, x2, y2 = person

    # الجسم (ملابس)
    frame[y1:y2, x1:x2] = (60, 60, 60)
    # الرأس: جلد + عينين داكنتين
    hx1, hy1, hx2, hy2 = head_box(person, 0.32)
    frame[hy1:hy2, hx1:hx2] = SKIN_BGR
    eye_y = hy1 + int((hy2 - hy1) * 0.42)
    eye_h = max(4, (hy2 - hy1) // 9)
    eye_w = max(4, (hx2 - hx1) // 9)
    for ratio in (0.22, 0.78):
        ex = hx1 + int((hx2 - hx1) * ratio)
        frame[eye_y : eye_y + eye_h, ex : ex + eye_w] = (10, 10, 10)

    # مناطق اليدين: جلد سميك
    for bx1, by1, bx2, by2 in hand_candidate_boxes(person):
        frame[by1:by2, bx1:bx2] = SKIN_BGR
        del bx1, by1, bx2, by2

    return frame


def test_person_box_and_lower_face_are_skin_free_of_goggles():
    frame = frame_with_person()
    assert frame.shape[:2] == (480, 640)
    lower = lower_face_box(head_box((200, 40, 420, 460), 0.32))
    assert lower[3] > lower[1]


# ---------------------------------------------------------------------------
# Merging / canonical names
# ---------------------------------------------------------------------------


def test_canonical_names_unify_medical_and_construction():
    assert canonical_class_name("no goggle") == canonical_class_name("NO-Goggles") == "NO-Goggles"
    assert canonical_class_name("hand gloves") == "Gloves"
    assert canonical_class_name("no mask") == "NO-Mask"
    assert class_key("NO-Head Cap") == class_key("no head cap")


def test_hybrid_merges_and_dedupes_same_class():
    construction = StubDetector([det("Person", (0, 0, 100, 300))])
    medical = StubDetector([det("no mask", (10, 10, 60, 60), 0.9), det("NO-Mask", (12, 12, 58, 58), 0.7)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
    )

    detections = hybrid.detect(frame_with_person())
    names = [canonical_class_name(d.class_name) for d in detections]

    assert names.count("NO-Mask") == 1
    assert "Person" in names  # فئة الشخص بتيجي من الموديل الإنشائي
    assert hybrid.last_stats.duplicates == 1
    assert hybrid.last_stats.medical == 2


def test_hybrid_disabled_falls_back_to_single_model():
    construction = StubDetector([det("Person", (0, 0, 10, 10))])
    medical = StubDetector([det("mask", (0, 0, 10, 10))])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
        enabled=False,
    )

    hybrid.detect(frame_with_person())
    assert medical.calls == 1
    assert construction.calls == 0


def test_medical_profile_uses_construction_assist_and_fuses_confidence():
    construction = StubDetector([det("Person", (0, 0, 100, 300)), det("Goggles", (10, 10, 60, 60), 0.6)])
    medical = StubDetector([det("goggle", (12, 12, 58, 58), 0.7)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
        run_construction_assist=True,
    )

    detections = hybrid.detect(frame_with_person())
    goggles = [d for d in detections if canonical_class_name(d.class_name) == "Goggles"]

    assert len(goggles) == 1
    assert goggles[0].confidence > 0.7  # confidence fusion
    assert "+" in goggles[0].source


def test_conflicting_positive_and_negative_resolved_by_confidence():
    construction = StubDetector([])
    medical = StubDetector(
        [
            det("mask", (10, 10, 60, 60), 0.9),
            det("no mask", (12, 12, 58, 58), 0.4),
        ]
    )
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
    )

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame_with_person())]
    assert "Mask" in names
    assert "NO-Mask" not in names
    assert hybrid.last_stats.conflicts == 1


def test_construction_profile_can_run_medical_assist_when_enabled():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    medical = StubDetector([det("no mask", (250, 60, 300, 100), 0.8)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="construction",
        config=HybridConfig(skin_filter_enabled=False),
        run_medical_assist=True,
    )

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame_with_person())]
    assert "NO-Mask" in names
    assert medical.calls == 1


# ---------------------------------------------------------------------------
# Skin layer
# ---------------------------------------------------------------------------


def test_eye_bridge_emits_no_goggles_for_bare_face():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    hybrid = HybridPPEDetector(construction, None, primary_profile="construction")

    detections = hybrid.detect(frame_with_person())
    no_goggles = [d for d in detections if canonical_class_name(d.class_name) == "NO-Goggles"]

    assert len(no_goggles) == 1
    assert no_goggles[0].source == SOURCE_EYE_BRIDGE
    assert no_goggles[0].confidence >= 0.45
    assert hybrid.last_stats.eye_bridge_hits == 1


def test_eye_bridge_downgrades_weak_goggle_detection():
    construction = StubDetector([det("Person", (200, 40, 420, 460)), det("Goggles", (240, 50, 380, 110), 0.5)])
    hybrid = HybridPPEDetector(construction, None, primary_profile="construction")

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame_with_person())]
    assert "Goggles" not in names
    assert "NO-Goggles" in names


def test_mouth_skin_emits_no_mask():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    hybrid = HybridPPEDetector(construction, None, primary_profile="construction")

    detections = hybrid.detect(frame_with_person())
    no_mask = [d for d in detections if canonical_class_name(d.class_name) == "NO-Mask"]

    assert len(no_mask) == 1
    assert no_mask[0].source == SOURCE_MOUTH
    assert hybrid.last_stats.mouth_skin_hits == 1


def test_bare_hand_detected_via_distance_transform():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    hybrid = HybridPPEDetector(construction, None, primary_profile="construction")

    detections = hybrid.detect(frame_with_person())
    no_gloves = [d for d in detections if canonical_class_name(d.class_name) == "NO-Gloves"]

    assert no_gloves, "لازم كشف يد عارية عبر distanceTransform"
    assert no_gloves[0].source == SOURCE_HAND
    assert hybrid.last_stats.bare_hands >= 1


def test_fake_glove_on_bare_skin_is_downgraded():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    medical = StubDetector([det("hand gloves", (200, 250, 280, 450), 0.55)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        run_construction_assist=True,
    )

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame_with_person())]
    assert "Gloves" not in names
    assert "NO-Gloves" in names


def test_confident_glove_detection_is_not_downgraded():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    medical = StubDetector([det("hand gloves", (200, 250, 280, 450), 0.95)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        run_construction_assist=True,
    )

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame_with_person())]
    assert "Gloves" in names


def test_gloved_hand_region_not_flagged_as_bare():
    frame = frame_with_person()
    # نغطي مناطق اليدين بقفاز أزرق
    for bx1, by1, bx2, by2 in hand_candidate_boxes((200, 40, 420, 460)):
        frame[by1:by2, bx1:bx2] = BLUE_GLOVE_BGR

    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    hybrid = HybridPPEDetector(construction, None, primary_profile="construction")

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame)]
    assert "NO-Gloves" not in names


def test_skin_layer_can_be_disabled():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    hybrid = HybridPPEDetector(
        construction,
        None,
        primary_profile="construction",
        config=HybridConfig(skin_filter_enabled=False),
    )

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame_with_person())]
    assert names == ["Person"]


def test_no_person_no_skin_synthetic_detections():
    construction = StubDetector([det("Hardhat", (10, 10, 60, 60))])
    hybrid = HybridPPEDetector(construction, None, primary_profile="construction")

    names = [canonical_class_name(d.class_name) for d in hybrid.detect(frame_with_person())]
    assert names == ["Hardhat"]
    assert hybrid.last_stats.synthetic == 0


def test_last_stats_are_exposed():
    construction = StubDetector([det("Person", (200, 40, 420, 460))])
    hybrid = HybridPPEDetector(construction, None, primary_profile="construction")
    hybrid.detect(frame_with_person())

    stats = hybrid.last_stats.as_dict()
    assert set(stats) >= {"construction", "medical", "merged", "bare_hands", "eye_bridge_hits", "synthetic"}
    assert stats["merged"] >= 1


def test_goggles_and_no_goggles_never_coexist_in_same_frame():
    """
    إصلاح المشكلة #2: عندما يكتشف الموديل الطبي Goggles بثقة أعلى من سقف الإسقاط
    (أو يكون فلتر جسر الأنف ضعيف الثقة)، لا يصح ظهور Goggles و NO-Goggles معاً.
    """
    construction = StubDetector([det("Person", (200, 40, 420, 460), 0.68)])
    medical = StubDetector([det("goggle", (250, 60, 360, 100), 0.68)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        run_construction_assist=True,
    )

    detections = hybrid.detect(frame_with_person(), profile="medical")
    names = [canonical_class_name(d.class_name) for d in detections]

    assert "Goggles" in names
    assert "NO-Goggles" not in names


def test_cross_model_goggles_with_different_box_sizes_merge():
    """
    إصلاح المشكلة #3 (ب): الموديل الإنشائي والطبي يكتشفان Goggles بحجمين مختلفين
    (IoU < 0.55 لكن أحدهما محتوى داخل الآخر) -> يندمجان في كشف واحد مع تعزيز الثقة.
    """
    construction = StubDetector(
        [
            det("Person", (200, 40, 420, 460), 0.85),
            det("Goggles", (225, 48, 395, 122), 0.60),
        ]
    )
    medical = StubDetector([det("goggle", (250, 60, 365, 98), 0.52)])
    hybrid = HybridPPEDetector(
        construction,
        medical,
        primary_profile="medical",
        config=HybridConfig(skin_filter_enabled=False),
        run_construction_assist=True,
    )

    detections = hybrid.detect(frame_with_person(), profile="medical")
    goggles = [d for d in detections if canonical_class_name(d.class_name) == "Goggles"]

    assert len(goggles) == 1
    assert goggles[0].confidence > 0.60


def test_mouth_skin_does_not_duplicate_existing_head_no_mask():
    """
    إصلاح المشكلة #3 (أ): وجود NO-Mask من الموديل الإنشائي على الوجه (حتى لو
    احتواؤه مع النصف السفلي أقل من 0.45) لا ينتج NO-Mask ثانية من skin:mouth.
    """
    construction = StubDetector(
        [
            det("Person", (200, 40, 420, 460), 0.85),
            # مستطيل على الجزء العلوي/الأوسط من الرأس بحيث تقاطعه مع lower_face_box محدود
            det("NO-Mask", (220, 45, 400, 125), 0.96),
        ]
    )
    hybrid = HybridPPEDetector(
        construction,
        None,
        primary_profile="medical",
        run_construction_assist=True,
    )

    detections = hybrid.detect(frame_with_person(), profile="medical")
    no_masks = [d for d in detections if canonical_class_name(d.class_name) == "NO-Mask"]

    assert len(no_masks) == 1
    assert no_masks[0].confidence == 0.96
    assert "model:construction" in no_masks[0].source


def test_mouth_skin_merges_model_no_mask_slightly_below_estimated_head():
    """صندوقا الموديل والجلد المزاحان قليلًا على الوجه يظلان كشف NO-Mask واحدًا."""
    construction = StubDetector(
        [
            det("Person", (200, 40, 420, 460), 0.85),
            # مركز الصندوق أسفل حد head_box بقليل، لكنه ما زال يخص الوجه نفسه.
            det("NO-Mask", (225, 178, 395, 202), 0.96),
        ]
    )
    hybrid = HybridPPEDetector(
        construction,
        None,
        primary_profile="medical",
        run_construction_assist=True,
    )

    detections = hybrid.detect(frame_with_person(), profile="medical")
    no_masks = [d for d in detections if canonical_class_name(d.class_name) == "NO-Mask"]

    assert len(no_masks) == 1
    assert no_masks[0].confidence == 0.96
    assert "model:construction" in no_masks[0].source
    assert "skin:mouth" in no_masks[0].source


def test_expanded_face_anchor_does_not_merge_adjacent_people():
    """دمج الوجه لا يبتلع مخالفة شخص مجاور في مشهد مزدحم."""
    person_boxes = [(70, 40, 270, 460), (370, 40, 570, 460)]
    frame = np.full((480, 640, 3), (90, 90, 90), dtype=np.uint8)
    detections = [det("Person", box, 0.85) for box in person_boxes]

    for person_box in person_boxes:
        x1, y1, x2, y2 = person_box
        frame[y1:y2, x1:x2] = (60, 60, 60)
        hx1, hy1, hx2, hy2 = head_box(person_box, 0.32)
        frame[hy1:hy2, hx1:hx2] = SKIN_BGR
        eye_y = hy1 + int((hy2 - hy1) * 0.42)
        eye_h = max(4, (hy2 - hy1) // 9)
        eye_w = max(4, (hx2 - hx1) // 9)
        for ratio in (0.22, 0.78):
            ex = hx1 + int((hx2 - hx1) * ratio)
            frame[eye_y : eye_y + eye_h, ex : ex + eye_w] = (10, 10, 10)

    # النموذج اكتشف NO-Mask على الشخص اليمين، قليلًا أسفل head_box.
    detections.append(det("NO-Mask", (385, 178, 555, 202), 0.96))
    hybrid = HybridPPEDetector(
        StubDetector(detections),
        None,
        primary_profile="medical",
        run_construction_assist=True,
    )

    output = hybrid.detect(frame, profile="medical")
    no_masks = [d for d in output if canonical_class_name(d.class_name) == "NO-Mask"]

    assert len(no_masks) == 2
    assert sum("model:construction" in d.source for d in no_masks) == 1
    assert sum("skin:mouth" in d.source for d in no_masks) == 2

