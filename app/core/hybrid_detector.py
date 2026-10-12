"""
Smart Hybrid Medical + Construction detector.

Why a hybrid?
-------------
* The construction model (`ppe.pt`) knows `Person`, helmets, vests and boots but
  is weak on hospital PPE.
* The medical model knows `mask`, `hand gloves`, `head cap`, `goggle`, `lab coat`
  ... but it has **no `Person` class at all**, so it cannot associate PPE items
  with people nor reason about "staff is present but the lab coat is missing".

:class:`HybridPPEDetector` runs both YOLO models on the same frame, normalises
every class name to one canonical vocabulary, merges duplicate boxes (with
cross-model confidence fusion) and then runs the smart skin layer:

* `calc_skin_ratio`            → is the region actually exposed skin?
* `distanceTransform` (bare hand) → bare-hand confirmation / glove downgrade.
* eye-bridge test (`NO-Goggles`)  → bridge of the nose is visible ⇒ no goggles.

The result is a single ``list[Detection]`` that the existing
``ConstructionViolationChecker`` / ``MedicalViolationChecker`` understand, so the
whole platform (streams, alerts, WebSocket counts) benefits without any API
change. Set ``HYBRID_DETECTION_ENABLED=false`` to fall back to the old
one-model-per-profile behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.core.detector import CLASS_COLORS_BY_NAME, Detection, PPEDetector, is_skin_source
from app.core.logging import get_logger
from app.core.ppe import (
    CONSTRUCTION_ONLY_CLASSES,
    Profile,
    canonical_class_name,
    class_key,
)
from app.core.skin_analysis import (
    EyeBridgeResult,
    SkinStats,
    analyze_skin_region,
    calc_skin_ratio,
    crop_region,
    eye_bridge_exposed,
    hand_candidate_boxes,
    head_box,
    lower_face_box,
    ratio_confidence,
)

logger = get_logger(__name__)

# فئات موجبة/سالبة متعارضة (لا يصح ظهور الاتنين على نفس المنطقة)
OPPOSITE_CLASSES: tuple[tuple[str, str], ...] = (
    ("Hardhat", "NO-Hardhat"),
    ("Safety Vest", "NO-Safety Vest"),
    ("Mask", "NO-Mask"),
    ("Gloves", "NO-Gloves"),
    ("Safety Boots", "NO-Safety Boots"),
    ("Goggles", "NO-Goggles"),
    ("Head Cap", "NO-Head Cap"),
)

# الفئات اللي بيتحقق منها فلتر الجلد
SKIN_CHECKED_CLASSES = ("NO-Mask", "Mask", "NO-Gloves", "Gloves", "NO-Goggles", "Goggles")

SYNTHETIC_CLASS_ID = -1
SOURCE_MODEL = "model"
SOURCE_EYE_BRIDGE = "skin:eye_bridge"
SOURCE_ANATOMICAL_BRIDGE = "skin:anatomical_bridge"
SOURCE_GLASS = "skin:glass_band"
SOURCE_MOUTH = "skin:mouth"
SOURCE_HAND = "skin:distance_transform"

# أقصى عدد وشوش يفحصها الجسر التشريحي في الفريم الواحد (تحديد تكلفة)
ANATOMICAL_BRIDGE_MAX_FACES = 4


@dataclass(frozen=True)
class HybridConfig:
    """إعدادات النظام الهجين + فلتر الجلد (تتبني من settings)."""

    merge_iou: float = 0.55
    conflict_iou: float = 0.30
    override_min_containment: float = 0.45
    head_region_ratio: float = 0.32
    skin_filter_enabled: bool = True
    bare_hand_enabled: bool = True
    eye_bridge_enabled: bool = True
    skin_min_ratio: float = 0.18
    skin_strong_ratio: float = 0.32
    glove_reject_ratio: float = 0.24
    bare_hand_min_thickness: float = 0.12
    bare_hand_min_area: float = 0.10
    eye_bridge_min_skin_ratio: float = 0.22
    glass_confirm_min_ratio: float = 0.05
    synthetic_min_conf: float = 0.45
    # ── حراس الدقة (Precision guards) ──
    synthetic_max_conf: float = 0.85
    skin_negative_min_conf: float = 0.70
    skin_min_person_conf: float = 0.35
    positive_override_max_conf: float = 0.60
    positive_override_min_conf: float = 0.70

    @classmethod
    def from_settings(cls, s=settings) -> HybridConfig:
        return cls(
            merge_iou=s.HYBRID_MERGE_IOU,
            conflict_iou=s.HYBRID_CONFLICT_IOU,
            override_min_containment=s.HYBRID_OVERRIDE_MIN_CONTAINMENT,
            head_region_ratio=s.HYBRID_HEAD_REGION_RATIO,
            skin_filter_enabled=s.SKIN_FILTER_ENABLED,
            bare_hand_enabled=s.SKIN_BARE_HAND_ENABLED,
            eye_bridge_enabled=s.SKIN_EYE_BRIDGE_ENABLED,
            skin_min_ratio=s.SKIN_MIN_RATIO,
            skin_strong_ratio=s.SKIN_STRONG_RATIO,
            glove_reject_ratio=s.SKIN_GLOVE_REJECT_RATIO,
            bare_hand_min_thickness=s.SKIN_BARE_HAND_MIN_THICKNESS,
            bare_hand_min_area=s.SKIN_BARE_HAND_MIN_AREA,
            eye_bridge_min_skin_ratio=s.SKIN_EYE_BRIDGE_MIN_SKIN_RATIO,
            glass_confirm_min_ratio=s.SKIN_GLASS_CONFIRM_MIN_RATIO,
            synthetic_min_conf=s.SKIN_SYNTHETIC_MIN_CONF,
            synthetic_max_conf=s.SKIN_SYNTHETIC_MAX_CONF,
            skin_negative_min_conf=s.SKIN_NEGATIVE_MIN_CONF,
            skin_min_person_conf=s.SKIN_MIN_PERSON_CONF,
            positive_override_max_conf=s.SKIN_POSITIVE_OVERRIDE_MAX_CONF,
            positive_override_min_conf=s.SKIN_POSITIVE_OVERRIDE_MIN_CONF,
        )


@dataclass
class HybridStats:
    """إحصاءات آخر فريم (لوج + إمكانية المراقبة)."""

    construction: int = 0
    medical: int = 0
    merged: int = 0
    duplicates: int = 0
    conflicts: int = 0
    bridged: int = 0
    bare_hands: int = 0
    eye_bridge_hits: int = 0
    glass_confirmations: int = 0
    mouth_skin_hits: int = 0
    synthetic: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "construction": self.construction,
            "medical": self.medical,
            "merged": self.merged,
            "duplicates": self.duplicates,
            "conflicts": self.conflicts,
            "bridged": self.bridged,
            "bare_hands": self.bare_hands,
            "eye_bridge_hits": self.eye_bridge_hits,
            "glass_confirmations": self.glass_confirmations,
            "mouth_skin_hits": self.mouth_skin_hits,
            "synthetic": self.synthetic,
        }


def _iou_boxes(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(1, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(1, (b[2] - b[0]) * (b[3] - b[1]))
    return inter / float(area_a + area_b - inter)


def detection_box(det: Detection) -> tuple[int, int, int, int]:
    return (det.x1, det.y1, det.x2, det.y2)


def _containment(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """نسبة تغطية المستطيل الأصغر — أدق من IoU لما نقارن بوكس صغير بمنطقة كبيرة."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(1, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(1, (b[2] - b[0]) * (b[3] - b[1]))
    return inter / float(min(area_a, area_b))


def _iou(a: Detection, b: Detection) -> float:
    return _iou_boxes(detection_box(a), detection_box(b))


def _make_detection(class_name: str, confidence: float, box: tuple[int, int, int, int], source: str) -> Detection:
    x1, y1, x2, y2 = box
    return Detection(
        class_id=SYNTHETIC_CLASS_ID,
        class_name=class_name,
        confidence=float(round(min(0.99, max(0.0, confidence)), 4)),
        x1=int(x1),
        y1=int(y1),
        x2=int(x2),
        y2=int(y2),
        color=CLASS_COLORS_BY_NAME.get(class_name, (255, 255, 0)),
        source=source,
    )


class HybridPPEDetector:
    """
    دمج موديلين + طبقة فلتر الجلد الذكية.

    ``detect(frame)`` واجهة متوافقة مع ``PPEDetector`` حتى يعمل الكاميرا
    مانجر وكل الاختبارات القديمة بدون أي تعديل.
    """

    def __init__(
        self,
        construction: PPEDetector | None,
        medical: PPEDetector | None = None,
        *,
        primary_profile: Profile = "construction",
        config: HybridConfig | None = None,
        run_medical_assist: bool | None = None,
        run_construction_assist: bool | None = None,
        enabled: bool = True,
    ) -> None:
        self.construction = construction
        self.medical = medical
        self.primary_profile: Profile = primary_profile
        self.config = config or HybridConfig.from_settings()
        self.enabled = enabled

        # هل نشغّل الموديل التاني كمساعد للبروفايل الحالي؟
        self.run_medical_assist = (
            settings.HYBRID_MEDICAL_ON_CONSTRUCTION if run_medical_assist is None else run_medical_assist
        )
        self.run_construction_assist = (
            settings.HYBRID_CONSTRUCTION_ON_MEDICAL
            if run_construction_assist is None
            else run_construction_assist
        )
        self.last_stats = HybridStats()

        logger.info(
            "HybridPPEDetector ready (primary=%s, hybrid_enabled=%s, medical_assist=%s, construction_assist=%s, "
            "skin_filter=%s, bare_hand=%s, eye_bridge=%s)",
            primary_profile,
            enabled,
            self.run_medical_assist,
            self.run_construction_assist,
            self.config.skin_filter_enabled,
            self.config.bare_hand_enabled,
            self.config.eye_bridge_enabled,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def class_names(self) -> dict[str, dict[int, str]]:
        return {
            "construction": dict(self.construction.class_names) if self.construction else {},
            "medical": dict(self.medical.class_names) if self.medical else {},
        }

    def _active_detectors(self, profile: Profile) -> list[tuple[str, PPEDetector]]:
        active: list[tuple[str, PPEDetector]] = []
        if not self.enabled:
            primary = self.construction if profile == "construction" else self.medical
            fallback = self.construction or self.medical
            detector = primary or fallback
            if detector is not None:
                active.append((profile, detector))
            return active

        if profile == "construction":
            if self.construction is not None:
                active.append(("construction", self.construction))
            if self.medical is not None and self.run_medical_assist:
                active.append(("medical", self.medical))
        else:
            if self.medical is not None:
                active.append(("medical", self.medical))
            if self.construction is not None and self.run_construction_assist:
                active.append(("construction", self.construction))
        return active

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, profile: Profile | None = None) -> list[Detection]:
        profile = profile or self.primary_profile
        stats = HybridStats()

        raw: list[Detection] = []
        for source_name, detector in self._active_detectors(profile):
            found = list(detector.detect(frame))
            for det in found:
                det.class_name = canonical_class_name(det.class_name)
                if not is_skin_source(det.source):
                    # كل موديل ليه وسم مختلف => نقدر نميّز الاتفاق بين الموديلين
                    det.source = f"{SOURCE_MODEL}:{source_name}"
            if source_name == "construction":
                stats.construction = len(found)
            else:
                stats.medical = len(found)
            if profile == "medical" and source_name == "construction":
                # الجسر الإنشائي: نعدي للبروفايل الطبي الكشوف اللي تفيده فقط
                found = self._bridge_construction_to_medical(found, stats)
            raw.extend(found)

        merged, duplicates = self._merge(raw)
        stats.duplicates = duplicates
        merged, conflicts = self._resolve_conflicts(merged)
        stats.conflicts = conflicts

        if self.config.skin_filter_enabled and frame is not None:
            merged = self._apply_skin_heuristics(frame, merged, stats)
            merged, post_duplicates = self._merge(merged)
            stats.duplicates += post_duplicates
            merged, post_conflicts = self._resolve_conflicts(merged)
            stats.conflicts += post_conflicts

        if profile == "medical":
            # فايروول نهائي: كاميرا طبي مينفعش على الإطلاق تطلّع فئة إنشائية
            # (خوذة/فيست/بوت) من أي مصدر كان — الجسر الإنشائي بينظّف مخرجات
            # الموديل الإنشائي، وده بيضمن إن أي مسار تاني (فلاتر، دمج، مستقبلًا)
            # متقدرش تعدي كاميرا طبية بكشف إنشائي.
            merged = [d for d in merged if canonical_class_name(d.class_name) not in CONSTRUCTION_ONLY_CLASSES]

        stats.merged = len(merged)
        stats.synthetic = sum(1 for d in merged if d.class_id == SYNTHETIC_CLASS_ID)
        self.last_stats = stats
        return merged

    # ------------------------------------------------------------------
    # Construction → Medical bridge
    # ------------------------------------------------------------------

    def _bridge_construction_to_medical(
        self, detections: list[Detection], stats: HybridStats
    ) -> list[Detection]:
        """
        الجسر الإنشائي للبروفايل الطبي.

        الموديل الطبي معندوش فئة ``Person`` خالص، فكاميرات المستشفيات بتستعين
        بالموديل الإنشائي. بس مش كل كشوفه تفيد هنا: الخوذة/الفيست/البوت
        فئات إنشائية خالصة، ولو دخلت البروفايل الطبي هتلوّث العدادات والعرض.
        الجسر بيعدي بس:

        * ``Person`` — لربط القطع بالأشخاص وتمكين فحص "الطاقم موجود والبالطو غايب".
        * القطع المشتركة بين القطاعين (الكمامة/النظارة/الجوانتي) بأسمائها الموحّدة.

        ويتم تسجيل عدد الكشوف المعبّرة في ``stats.bridged`` للمراقبة.
        """
        bridged: list[Detection] = []
        for det in detections:
            if canonical_class_name(det.class_name) in CONSTRUCTION_ONLY_CLASSES:
                logger.debug(
                    "construction->medical bridge dropped %s (construction-only class)",
                    det.class_name,
                )
                continue
            bridged.append(det)
        stats.bridged += len(bridged)
        return bridged

    # ------------------------------------------------------------------
    # Merging & conflict resolution
    # ------------------------------------------------------------------

    def _same_region(
        self,
        box_a: tuple[int, int, int, int],
        box_b: tuple[int, int, int, int],
        *,
        anchor_box: tuple[int, int, int, int] | None = None,
    ) -> bool:
        """هل المستطيلان يمثّلان نفس المنطقة التشريحية (مع مراعاة الاحتواء أو المرجع كالرأس)؟"""
        if _iou_boxes(box_a, box_b) >= self.config.conflict_iou:
            return True
        if _containment(box_a, box_b) >= self.config.override_min_containment:
            return True
        return bool(
            anchor_box is not None
            and (
                _containment(box_a, anchor_box) >= self.config.override_min_containment
                or _iou_boxes(box_a, anchor_box) >= self.config.conflict_iou
                or _center_inside(box_a, anchor_box)
            )
        )

    def _merge(self, detections: list[Detection]) -> tuple[list[Detection], int]:
        """
        دمج كشوف الموديلين: تفضيل الأعلى ثقة + تعزيز الثقة عند اتفاق الموديلين
        على نفس الفئة ونفس المكان (confidence fusion).

        يأخذ في الحسبان اختلاف حجم المستطيل بين الموديلين (أحدهما ضيق حول العينين
        أو الفم والآخر أوسع على الوجه) عبر الاحتواء ``_containment`` وتقاطع المصادر
        المختلفة حتى لا تتكرر ``Goggles`` أو ``NO-Mask`` مرتين لنفس الشخص.
        """
        kept: list[Detection] = []
        duplicates = 0

        for det in sorted(detections, key=lambda d: d.confidence, reverse=True):
            key = class_key(det.class_name)
            det_box = detection_box(det)
            matched: Detection | None = None
            for existing in kept:
                if class_key(existing.class_name) != key:
                    continue
                existing_box = detection_box(existing)
                same_box = (
                    _iou(det, existing) >= self.config.merge_iou
                    or _containment(det_box, existing_box) >= self.config.override_min_containment
                    or (
                        existing.source != det.source
                        and _iou(det, existing) >= self.config.conflict_iou
                    )
                )
                if same_box:
                    matched = existing
                    break

            if matched is None:
                kept.append(det)
                continue

            duplicates += 1
            if matched.source != det.source:
                matched_is_skin = is_skin_source(matched.source)
                det_is_skin = is_skin_source(det.source)
                if matched_is_skin and not det_is_skin:
                    # الكشف الموديلي أولى بقيادة المصدر والمستطيل من الكشف الصناعي
                    matched.confidence = max(matched.confidence, det.confidence)
                    matched.source = f"{det.source}+{matched.source}"
                    matched.class_id = det.class_id
                    matched.x1, matched.y1, matched.x2, matched.y2 = (
                        det.x1,
                        det.y1,
                        det.x2,
                        det.y2,
                    )
                elif det_is_skin and not matched_is_skin:
                    # دمج كشف جلد صناعي في كشف موديلي قائم دون تضخيم المستطيل
                    matched.confidence = max(matched.confidence, det.confidence)
                    if det.source not in matched.source:
                        matched.source = f"{matched.source}+{det.source}"
                else:
                    # اتفاق موديلين مختلفين => ثقة أعلى ومستطيل شامل
                    fused = max(matched.confidence, det.confidence) + 0.10 * min(
                        matched.confidence, det.confidence
                    )
                    matched.confidence = float(round(min(0.99, fused), 4))
                    if det.source not in matched.source:
                        matched.source = f"{matched.source}+{det.source}"
                    matched.x1 = min(matched.x1, det.x1)
                    matched.y1 = min(matched.y1, det.y1)
                    matched.x2 = max(matched.x2, det.x2)
                    matched.y2 = max(matched.y2, det.y2)

        return kept, duplicates

    def _resolve_conflicts(self, detections: list[Detection]) -> tuple[list[Detection], int]:
        """
        يشيل التعارض بين فئة موجبة وسالبة على نفس المنطقة (مثل ``Goggles`` و ``NO-Goggles``).

        * يعتمد على ``conflict_iou`` أو الاحتواء ``override_min_containment`` لأن بوكس
          النظارة من الموديل بيكون أصغر وجوه بوكس الرأس من فلتر الجلد.
        * الكشف السالب الصناعي (``skin:*``) لا يُسقط كشف الموديل الموجب إلا لو حقق
          شروط ``positive_override_min_conf`` و ``positive_override_max_conf``.
        """
        by_key: dict[str, list[Detection]] = {}
        for det in detections:
            by_key.setdefault(class_key(det.class_name), []).append(det)

        removed_ids: set[int] = set()
        conflicts = 0
        for positive, negative in OPPOSITE_CLASSES:
            positives = by_key.get(class_key(positive), [])
            negatives = by_key.get(class_key(negative), [])
            for neg in negatives:
                if id(neg) in removed_ids:
                    continue
                neg_box = detection_box(neg)
                for pos in positives:
                    if id(pos) in removed_ids:
                        continue
                    pos_box = detection_box(pos)
                    if (
                        _iou(pos, neg) < self.config.conflict_iou
                        and _containment(pos_box, neg_box) < self.config.override_min_containment
                    ):
                        continue

                    neg_is_skin = is_skin_source(neg.source)
                    pos_is_skin = is_skin_source(pos.source)
                    if neg_is_skin and not pos_is_skin:
                        can_override = (
                            neg.confidence >= self.config.positive_override_min_conf
                            and pos.confidence <= self.config.positive_override_max_conf
                        )
                        loser = pos if can_override else neg
                    elif pos_is_skin and not neg_is_skin:
                        loser = pos if pos.confidence <= neg.confidence else neg
                    else:
                        loser = neg if neg.confidence <= pos.confidence else pos

                    removed_ids.add(id(loser))
                    conflicts += 1
                    if loser is neg:
                        break

        if not removed_ids:
            return detections, conflicts
        return [d for d in detections if id(d) not in removed_ids], conflicts

    # ------------------------------------------------------------------
    # Smart skin layer
    # ------------------------------------------------------------------

    def _has_conflicting_positive(
        self,
        detections: list[Detection],
        positive_name: str,
        box: tuple[int, int, int, int],
        *,
        anchor_box: tuple[int, int, int, int] | None = None,
    ) -> bool:
        """هل توجد فئة موجبة قائمة على نفس المنطقة لم يتم إسقاطها؟"""
        target = class_key(positive_name)
        return any(
            class_key(det.class_name) == target
            and self._same_region(detection_box(det), box, anchor_box=anchor_box)
            for det in detections
        )

    def _upsert(
        self,
        detections: list[Detection],
        class_name: str,
        confidence: float,
        box: tuple[int, int, int, int],
        source: str,
        *,
        boost: bool = True,
        anchor_box: tuple[int, int, int, int] | None = None,
    ) -> Detection:
        """
        يضيف كشف جديد أو يعزّز كشف قائم لنفس الفئة على نفس المنطقة.

        مهم: الكشوف المُصنّعة (source=skin:*) بتتضاف بعد فلترة الثقة، فبتوصل
        للـ violation checker على طول. وعند تمرير ``anchor_box`` (مثل مستطيل
        الرأس كاملًا) يندمج كشف الفم/العينين مع كشف الموديل الموجود لنفس الرأس
        بدل إضافة مستطيل ثانٍ مكرر لنفس الفئة.
        """
        for det in detections:
            if class_key(det.class_name) != class_key(class_name):
                continue
            if self._same_region(detection_box(det), box, anchor_box=anchor_box):
                if boost:
                    det.confidence = max(det.confidence, float(round(confidence, 4)))
                    if source not in det.source:
                        det.source = f"{det.source}+{source}"
                return det

        new_det = _make_detection(class_name, confidence, box, source)
        detections.append(new_det)
        return new_det

    def _drop(
        self,
        detections: list[Detection],
        class_name: str,
        box: tuple[int, int, int, int],
        *,
        max_conf: float,
        anchor_box: tuple[int, int, int, int] | None = None,
    ) -> int:
        """
        يشيل كشف موجَب اتبيّن إنه غلط (الجلد مكشوف تحته) بشرط إن ثقته مش عالية جدًا.
        """
        removed = 0
        keep: list[Detection] = []
        for det in detections:
            if (
                class_key(det.class_name) == class_key(class_name)
                and det.confidence <= max_conf
                and self._same_region(detection_box(det), box, anchor_box=anchor_box)
            ):
                removed += 1
                continue
            keep.append(det)
        if removed:
            detections[:] = keep
        return removed

    def _skin_confidence(self, base: float) -> float:
        """
        ثقة معيارية للكشوف الصناعية: محصورة بين أرضية ``synthetic_min_conf``
        وسقف ``synthetic_max_conf``.

        السقف مهم للدقة: الهوريستيك (نسبة جلد / distanceTransform) مش موديل
        مُدرَّب — مينفعش يطلع بثقة 0.96 زي ما ظهر في اللوج، لأن الثقة العالية
        دي بتتحول لمخالفات مسجّلة وإنذارات على دليل ضعيف.
        """
        return float(
            round(
                max(self.config.synthetic_min_conf, min(self.config.synthetic_max_conf, base)),
                4,
            )
        )

    def _apply_skin_heuristics(
        self, frame: np.ndarray, detections: list[Detection], stats: HybridStats
    ) -> list[Detection]:
        # الفحوصات التشريحية (رأس/فم/يدين) محتاجة مرجع موثوق — Person ضعيف
        # (تحت skin_min_person_conf) معناه مستطيل مش مضمون على حد شخص أصلاً،
        # والفحص عليه بيطلع كشوف وهمية كل فريم (زي Person 0.26 في اللوج).
        persons = [
            d
            for d in detections
            if canonical_class_name(d.class_name) == "Person"
            and d.confidence >= self.config.skin_min_person_conf
        ]
        if not persons:
            # مفيش Person موثوق في الكادر (كاميرا طبية والمساعد الإنشائي مقفول
            # مثلًا) — الجسر التشريحي بيستخدم الكمامة المكتشفة كمرجع تشريحي
            # لفحص خط العينين (الكمامة نفسها عدّت عتبة فئتها بالفعل).
            if self.config.eye_bridge_enabled:
                self._append_anatomical_eye_bridge(frame, detections, stats)
            return detections

        for person in persons:
            person_box = detection_box(person)
            head = head_box(person_box, self.config.head_region_ratio)

            if self.config.eye_bridge_enabled:
                self._check_eye_bridge(frame, detections, head, stats)

            self._check_mouth_skin(frame, detections, head, stats)

        # اليدين بتتفحص مرة واحدة على مستوى الفريم (مع ربط كل قفاز بأقرب شخص)
        self._verify_glove_detections(frame, detections, persons, stats)

        return detections

    def _check_eye_bridge(
        self, frame: np.ndarray, detections: list[Detection], head: tuple[int, int, int, int], stats: HybridStats
    ) -> None:
        """كشف الوش المكشوف ما بين العينين => ``NO-Goggles``."""
        if min(head[2] - head[0], head[3] - head[1]) < 16:
            return

        face = crop_region(frame, head, pad=0.05)
        if face is None:
            return

        result: EyeBridgeResult = eye_bridge_exposed(
            face, min_skin_ratio=self.config.eye_bridge_min_skin_ratio
        )
        if not result.exposed:
            # شريط زجاجي على خط العينين => تأكيد إن النظارة موجودة فعلاً
            # (بشرط عدم وجود كشف سالب صريح من الموديل على نفس الرأس)
            if result.glass_ratio >= self.config.glass_confirm_min_ratio and not self._has_conflicting_positive(
                detections, "NO-Goggles", head, anchor_box=head
            ):
                confidence = self._skin_confidence(
                    0.50
                    + 0.45
                    * ratio_confidence(
                        result.glass_ratio, self.config.glass_confirm_min_ratio, 0.25
                    )
                )
                self._upsert(detections, "Goggles", confidence, head, SOURCE_GLASS, anchor_box=head)
                stats.glass_confirmations += 1
                logger.debug("glass band confirmed goggles: ratio=%.2f", result.glass_ratio)
            return

        confidence = self._skin_confidence(result.confidence)
        # الوش مكشوف => لو فيه كشف نظارة ضعيف على نفس المنطقة نشيله أولاً
        # (لازم الهوريستيك نفسه واثق بدرجة كافية كمان — positive_override_min_conf)
        removed = 0
        if confidence >= self.config.positive_override_min_conf:
            removed = self._drop(
                detections,
                "Goggles",
                head,
                max_conf=self.config.positive_override_max_conf,
                anchor_box=head,
            )

        # إذا بقيت نظارة موجبة من الموديل على نفس الرأس، لا نضيف NO-Goggles فوقها
        # حتى لا يظهر Goggles و NO-Goggles معاً في نفس الفريم
        if self._has_conflicting_positive(detections, "Goggles", head, anchor_box=head):
            return

        boosted_conf = self._skin_confidence(confidence + 0.05) if removed else confidence
        self._upsert(detections, "NO-Goggles", boosted_conf, head, SOURCE_EYE_BRIDGE, anchor_box=head)
        stats.eye_bridge_hits += 1

        logger.debug(
            "eye-bridge: skin_ratio=%.2f eyes=%d conf=%.2f",
            result.skin_ratio,
            result.eyes_found,
            confidence,
        )

    @staticmethod
    def _eye_zone_above_mask(box: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
        """
        منطقة خط العينين المستنتجة تشريحيًا من بوكس الكمامة.

        الكمامة بتغطي الأنف والفم، فخط العينين/جسر الأنف بيكون مباشرة فوق حافتها
        العليا: ناخد شريطًا عرضه أعرض شوية من الكمامة وارتفاعه ممتد لفوق.
        """
        x1, y1, x2, y2 = box
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        zx1 = x1 - int(w * 0.15)
        zx2 = x2 + int(w * 0.15)
        zy1 = y1 - int(h * 0.85)
        zy2 = y1 + int(h * 0.25)
        if zx2 - zx1 < 16 or zy2 - zy1 < 16:
            return None
        return (zx1, zy1, zx2, zy2)

    def _append_anatomical_eye_bridge(
        self, frame: np.ndarray, detections: list[Detection], stats: HybridStats
    ) -> None:
        """
        الجسر التشريحي (Anatomical Eye Bridge).

        فحص جسر العينين الأصلي بيحتاج مستطيل ``Person`` عشان يستنتج منطقة الرأس،
        لكن كاميرات القطاع الطبي ممكن تشتغل من غير فئة Person (الموديل الطبي
        معندوش الفئة، والمساعد الإنشائي ممكن يكون مقفول). الحل: كل كشف ``Mask``
        هو دليل تشريحي — الوش موجود، وخط العينين فوق الكمامة مباشرة. نفحص
        الشريط ده بنفس اختبار ``eye_bridge_exposed`` ونضيف ``NO-Goggles`` لو
        جسر الأنف مكشوف، ونشيل أي ``Goggles`` ضعيفة على نفس المنطقة.
        """
        masks = [d for d in detections if canonical_class_name(d.class_name) == "Mask"]
        for mask in masks[:ANATOMICAL_BRIDGE_MAX_FACES]:
            zone = self._eye_zone_above_mask(detection_box(mask))
            if zone is None:
                continue

            face = crop_region(frame, zone, pad=0.05)
            if face is None:
                continue

            result: EyeBridgeResult = eye_bridge_exposed(
                face, min_skin_ratio=self.config.eye_bridge_min_skin_ratio
            )
            if not result.exposed:
                continue

            confidence = self._skin_confidence(result.confidence)
            removed = 0
            if confidence >= self.config.positive_override_min_conf:
                removed = self._drop(
                    detections,
                    "Goggles",
                    zone,
                    max_conf=self.config.positive_override_max_conf,
                    anchor_box=zone,
                )

            if self._has_conflicting_positive(detections, "Goggles", zone, anchor_box=zone):
                continue

            boosted_conf = self._skin_confidence(confidence + 0.05) if removed else confidence
            self._upsert(
                detections,
                "NO-Goggles",
                boosted_conf,
                zone,
                SOURCE_ANATOMICAL_BRIDGE,
                anchor_box=zone,
            )
            stats.eye_bridge_hits += 1

            logger.debug(
                "anatomical eye-bridge (mask anchor): skin_ratio=%.2f eyes=%d conf=%.2f",
                result.skin_ratio,
                result.eyes_found,
                confidence,
            )

    def _check_mouth_skin(
        self, frame: np.ndarray, detections: list[Detection], head: tuple[int, int, int, int], stats: HybridStats
    ) -> None:
        """كشف جلد الأنف/الفم => ``NO-Mask``."""
        # منطقة أصغر من كده مش وش مقروء — أي "جلد" فيها ضوضاء (رقبة/خلفية)
        if min(head[2] - head[0], head[3] - head[1]) < 24:
            return

        lower = lower_face_box(head, top=0.45)
        region = crop_region(frame, lower)
        if region is None:
            return

        ratio = calc_skin_ratio(region)
        if ratio < self.config.skin_strong_ratio:
            return

        upper = max(self.config.skin_strong_ratio * 1.6, min(0.75, self.config.skin_strong_ratio * 2.2))
        confidence = self._skin_confidence(
            0.55 + 0.40 * ratio_confidence(ratio, self.config.skin_strong_ratio, upper)
        )

        # إسقاط كمامة موجبة محتاج دليل أقوى بكتير (كان 0.55 بيأسد كشف Mask
        # لغاية 0.75 — ده كان بيقتل الكمامات الحقيقية ضعيفة الثقة)
        removed = 0
        if confidence >= self.config.positive_override_min_conf:
            removed = self._drop(
                detections,
                "Mask",
                lower,
                max_conf=self.config.positive_override_max_conf,
                anchor_box=head,
            )

        if self._has_conflicting_positive(detections, "Mask", lower, anchor_box=head):
            return

        boosted_conf = self._skin_confidence(confidence + 0.05) if removed else confidence
        self._upsert(
            detections,
            "NO-Mask",
            boosted_conf,
            lower,
            SOURCE_MOUTH,
            anchor_box=head,
        )
        stats.mouth_skin_hits += 1

        logger.debug("mouth-skin: ratio=%.2f conf=%.2f", ratio, confidence)

    def _verify_glove_detections(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        persons: list[Detection],
        stats: HybridStats,
    ) -> None:
        """
        كشف اليد العارية عبر ``distanceTransform``.

        * ``no hand gloves`` من الموديل → نأكّد الكشف ونديله ثقة الجلد (أو نمسح).
        * ``hand gloves`` والمنطقة جلد سميك فعلاً → قفاز وهمي، نقلبه لـ ``NO-Gloves``.
        * شخص من غير أي كشف قفازات → نمسح مناطق اليدين عندنا مباشرة.
        """
        if not self.config.bare_hand_enabled:
            return

        associated: list[int] = []  # indices of persons that already have glove evidence
        for det in list(detections):
            canonical = canonical_class_name(det.class_name)
            if canonical not in ("NO-Gloves", "Gloves"):
                continue

            box = detection_box(det)
            for idx, person in enumerate(persons):
                person_box = detection_box(person)
                if _iou_boxes(box, person_box) > 0.0 or _center_inside(box, person_box):
                    associated.append(idx)

            region = crop_region(frame, box, pad=0.08)
            if region is None:
                continue

            hand: SkinStats = analyze_skin_region(
                region,
                min_thickness=self.config.bare_hand_min_thickness,
                min_area=self.config.bare_hand_min_area,
            )

            if canonical == "NO-Gloves":
                if hand.is_bare:
                    boosted = max(det.confidence, self._skin_confidence(0.50 + 0.45 * hand.confidence))
                    det.confidence = boosted
                    if SOURCE_HAND not in det.source:
                        det.source = f"{det.source}+{SOURCE_HAND}"
                    stats.bare_hands += 1
                    logger.debug(
                        "bare-hand confirmed: thickness=%.2f ratio=%.2f blob=%.2f",
                        hand.thickness,
                        hand.skin_ratio,
                        hand.blob_area_ratio,
                    )
                continue

            # فئة موجبة (قفاز) لكن المنطقة جلد سميك => قفاز وهمي => يد عارية
            # نسبة رفض القفاز (glove_reject_ratio=0.24 افتراضيًا): ربع بوكس القفاز
            # جلد مكشوف كفاية لرفض الكشف — القفاز الحقيقي مبيبانوش جلد في نصه
            if (
                hand.is_bare
                and hand.skin_ratio >= self.config.glove_reject_ratio
                and det.confidence <= self.config.positive_override_max_conf
            ):
                self._drop(detections, "Gloves", box, max_conf=self.config.positive_override_max_conf)
                self._upsert(
                    detections,
                    "NO-Gloves",
                    self._skin_confidence(0.55 + 0.40 * hand.confidence),
                    box,
                    SOURCE_HAND,
                )
                stats.bare_hands += 1
                logger.debug(
                    "glove downgraded to NO-Gloves: thickness=%.2f ratio=%.2f reject_ratio=%.2f",
                    hand.thickness,
                    hand.skin_ratio,
                    self.config.glove_reject_ratio,
                )

        # أي شخص موثوق مالوش أي دليل قفاز في الفريم → نمسح مناطق اليدين بأنفسنا
        # (persons هنا فعلاً عدّت فلتر skin_min_person_conf)
        for idx, person in enumerate(persons):
            if idx in associated:
                continue
            self._scan_bare_hands(frame, detections, detection_box(person), stats)

    def _scan_bare_hands(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        person_box: tuple[int, int, int, int],
        stats: HybridStats,
    ) -> None:
        """مسح مناطق اليدين المرشحة داخل مستطيل الشخص بأداة distanceTransform."""
        best: tuple[float, tuple[int, int, int, int]] | None = None
        for candidate in hand_candidate_boxes(person_box):
            region = crop_region(frame, candidate)
            if region is None:
                continue
            hand = analyze_skin_region(
                region,
                min_thickness=self.config.bare_hand_min_thickness,
                min_area=self.config.bare_hand_min_area,
            )
            if not hand.is_bare:
                continue
            # مسح اليدين بيطلع كشوف وهمية بسهولة (خلفية/رقبة/وش جوه المستطيل
            # الجانبي) — لازم دليل قوي: جلد كثيف + ثقة تحليل كافية
            if hand.skin_ratio < self.config.skin_strong_ratio or hand.confidence < 0.5:
                continue
            score = hand.confidence * (0.5 + 0.5 * hand.skin_ratio)
            if best is None or score > best[0]:
                best = (score, candidate)

        if best is None:
            return

        score, candidate = best
        self._upsert(
            detections,
            "NO-Gloves",
            self._skin_confidence(0.45 + 0.45 * score),
            candidate,
            SOURCE_HAND,
        )
        stats.bare_hands += 1
        logger.debug("bare-hand scan hit: score=%.2f box=%s", score, candidate)


def _center_inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    cx = (inner[0] + inner[2]) // 2
    cy = (inner[1] + inner[3]) // 2
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]
