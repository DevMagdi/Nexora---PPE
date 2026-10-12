"""
Smart skin-based verification helpers for the hybrid detector.

A YOLO model alone is noisy on tiny PPE items (gloves, goggles, masks) and it
can never *prove* that bare skin is exposed. These helpers add cheap, fully
deterministic OpenCV checks on top of the model output:

* :func:`calc_skin_ratio` — dual-threshold (HSV + YCrCb) skin pixel ratio.
* :func:`analyze_skin_region` — bare-hand detector built on
  ``cv2.distanceTransform``: a real bare hand is a *thick* skin blob, while a
  gloved hand has almost no skin at all and stray skin pixels (wrists, arms,
  faces behind the box) produce only thin blobs.
* :func:`eye_bridge_exposed` — the `NO-Goggles` bridge test: if the strip
  *between* the two eyes (the nose bridge) is skin/eye coloured, then no goggles
  are worn, because goggles cover exactly that area.

Everything in this module is side-effect free, works on BGR ``numpy`` arrays and
never raises on degenerate input (empty / tiny crops return neutral values).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import cv2
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "EyeBridgeResult",
    "SkinStats",
    "analyze_skin_region",
    "calc_skin_ratio",
    "crop_region",
    "eye_bridge_exposed",
    "find_eye_boxes",
    "glass_band_ratio",
    "hand_candidate_boxes",
    "head_box",
    "lower_face_box",
    "ratio_confidence",
    "skin_region_mask",
]

# --- skin threshold constants (HSV + YCrCb, tuned for webcam/RTSP imagery) ---
HSV_H_MAX = 25  # OpenCV hue is 0..180
HSV_H_WRAP_MIN = 160
HSV_S_MIN = 28
HSV_V_MIN = 40
CR_MIN, CR_MAX = 133, 180
CB_MIN, CB_MAX = 77, 130

# --- eye/bridge constants ---
DARK_V_MAX = 75  # V channel value under which a pixel counts as "eye dark"
GLASS_S_MAX = 42  # تشبّع منخفض => زجاج/بلاستيك لامع
GLASS_V_MIN = 135
GLASS_ROW_FRACTION = 0.6  # نسبة عرض الصف اللي لو اتغطت بالزجاج يبقى فيه شريط نظارة
GLASS_BAND_MIN_ROWS = 0.04  # أقل نسبة ارتفاع للشريط الزجاجي
GLASS_BAND_MAX_ROWS = 0.45  # أكبر نسبة ارتفاع (الشريط أطول من كده يبقى مش عدسة)
GLASS_SCAN_TOP = 0.10  # منطقة البحث عن العدسة (خط العينين) داخل الوش
GLASS_SCAN_BOTTOM = 0.72
GLASS_CENTER_MAX = 0.62  # مركز الشريط لازم يكون في النص العلوي (العدسة مش كمامة)
GLASS_MIN_FACE_SKIN = 0.12  # نسبة الجلد المطلوبة فوق وتحت العدسة (وش مش شعر)

Box = tuple[int, int, int, int]

_EYE_CASCADE: cv2.CascadeClassifier | None = None
_EYE_CASCADE_READY = False


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------


def ratio_confidence(value: float, low: float, high: float) -> float:
    """يحوّل قيمة إلى ثقة 0..1 بتدريج خطي بين low و high."""
    if high <= low:
        return 1.0 if value >= high else 0.0
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return float((value - low) / (high - low))


def _clamp01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _is_usable(region: np.ndarray | None, min_side: int = 8) -> bool:
    if region is None or not isinstance(region, np.ndarray) or region.size == 0:
        return False
    if region.ndim < 2:
        return False
    return min(region.shape[0], region.shape[1]) >= min_side


def crop_region(frame: np.ndarray, box: Box, *, pad: float = 0.0) -> np.ndarray | None:
    """
    يقصّ منطقة من الفريم مع الحفاظ على الحدود.

    يرجع ``None`` لو المنطقة غير صالحة أو صغيرة جدًا.
    """
    if frame is None or frame.size == 0:
        return None

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in box)
    if pad > 0:
        pad_w = int((x2 - x1) * pad)
        pad_h = int((y2 - y1) * pad)
        x1, y1, x2, y2 = x1 - pad_w, y1 - pad_h, x2 + pad_w, y2 + pad_h

    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return frame[y1:y2, x1:x2]


# ---------------------------------------------------------------------------
# Skin mask & ratio
# ---------------------------------------------------------------------------


def skin_region_mask(region_bgr: np.ndarray) -> np.ndarray:
    """
    قناع الجلد (uint8 0/255) بدمج عتبتين: HSV (hue/saturation/value) و YCrCb.

    الدمج المنطقي (AND) يقلل الإيجابيات الكاذبة على الملابس الفاتحة والزجاج الشفاف.
    """
    if not _is_usable(region_bgr, min_side=3):
        return np.zeros((0, 0), dtype=np.uint8)

    if region_bgr.ndim == 2:
        region_bgr = cv2.cvtColor(region_bgr, cv2.COLOR_GRAY2BGR)

    blur = cv2.GaussianBlur(region_bgr, (3, 3), 0)
    hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
    ycrcb = cv2.cvtColor(blur, cv2.COLOR_BGR2YCrCb)

    hue, sat, val = cv2.split(hsv)
    _lum, cr, cb = cv2.split(ycrcb)

    hue_ok = (hue <= HSV_H_MAX) | (hue >= HSV_H_WRAP_MIN)
    hsv_ok = hue_ok & (sat >= HSV_S_MIN) & (val >= HSV_V_MIN)
    ycrcb_ok = (cr >= CR_MIN) & (cr <= CR_MAX) & (cb >= CB_MIN) & (cb <= CB_MAX)

    mask = (hsv_ok & ycrcb_ok).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return mask


def calc_skin_ratio(region_bgr: np.ndarray, mask: np.ndarray | None = None) -> float:
    """
    نسبة بكسلات الجلد في المنطقة (0.0 .. 1.0).

    دي الدالة الأساسية لفلتر الجلد: بتقول لنا قد إيه المنطقة مكشوفة فعلاً.
    """
    if mask is None:
        mask = skin_region_mask(region_bgr)
    if mask is None or mask.size == 0:
        return 0.0
    total = int(mask.shape[0] * mask.shape[1])
    if total <= 0:
        return 0.0
    return _clamp01(cv2.countNonZero(mask) / total)


@dataclass(frozen=True)
class SkinStats:
    """نتيجة تحليل منطقة: نسبة الجلد + سماكة الكتلة (distanceTransform)."""

    width: int = 0
    height: int = 0
    skin_ratio: float = 0.0
    thickness: float = 0.0  # max distanceTransform radius / min(h, w)
    blob_area_ratio: float = 0.0  # largest skin blob area / region area
    is_bare: bool = False
    confidence: float = 0.0

    @property
    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


def analyze_skin_region(
    region_bgr: np.ndarray,
    *,
    min_thickness: float = 0.12,
    min_area: float = 0.10,
) -> SkinStats:
    """
    كشف اليد العارية عبر ``cv2.distanceTransform``.

    الفكرة: بنحسب قناع الجلد، وبعدين distanceTransform بيدينا أقصى نصف قطر
    للكتلة الجلدية. اليد العارية كتلة سميكة ومتراصة، أما القفاز فمعندناش جلد
    أصلاً، والجلد العابر (رسغ، ذراع، وش بعيد) بيكون خطوط رقيقة.
    """
    if not _is_usable(region_bgr):
        return SkinStats()

    mask = skin_region_mask(region_bgr)
    if mask.size == 0:
        return SkinStats()

    h, w = mask.shape[:2]
    total = float(max(1, h * w))
    skin_pixels = int(cv2.countNonZero(mask))
    skin_ratio = _clamp01(skin_pixels / total)
    if skin_pixels == 0:
        return SkinStats(width=w, height=h)

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    peak = float(dist.max())
    thickness = _clamp01(peak / max(1.0, float(min(h, w))))

    blob_pixels = 0
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count > 1:
        blob_pixels = int(stats[1:, cv2.CC_STAT_AREA].max())
    blob_area_ratio = _clamp01(blob_pixels / total)

    is_bare = thickness >= min_thickness and blob_area_ratio >= min_area
    confidence = 0.5 * ratio_confidence(thickness, min_thickness, min_thickness * 2.5) + 0.5 * (
        ratio_confidence(blob_area_ratio, min_area, min_area * 3.0)
    )

    return SkinStats(
        width=w,
        height=h,
        skin_ratio=skin_ratio,
        thickness=thickness,
        blob_area_ratio=blob_area_ratio,
        is_bare=bool(is_bare),
        confidence=_clamp01(confidence),
    )


# ---------------------------------------------------------------------------
# Eye bridge (NO-Goggles)
# ---------------------------------------------------------------------------


def glass_band_ratio(region_bgr: np.ndarray) -> float:
    """واجهة عامة لقياس شريط الزجاج/النظارة (تُستخدم في تأكيد فئة Goggles)."""
    return _glass_band_ratio(region_bgr)


def _glass_band_ratio(region_bgr: np.ndarray) -> float:
    """
    نسبة ارتفاع "شريط زجاجي" في المنطقة.

    النظارة الواقية بتغطي خط العينين بشريط منخفض التشبع (زجاج فاتح/عاكس) أو
    معتم، وبيمتد أفقيًا على معظم عرض الوش. لو الشريط ده موجود يبقى فيه نظارة
    حتى لو الجلد ظاهر حواليه.
    """
    if not _is_usable(region_bgr, min_side=12):
        return 0.0

    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    glass = ((sat < GLASS_S_MAX) & (val > GLASS_V_MIN)) | (val < 60)
    row_fraction = glass.mean(axis=1)

    height = row_fraction.shape[0]
    top = max(0, int(height * GLASS_SCAN_TOP))
    bottom = max(top + 3, min(height, int(height * GLASS_SCAN_BOTTOM)))
    band = row_fraction[top:bottom] >= GLASS_ROW_FRACTION

    # لازم يكون فيه "وش" (جلد) فوق الشريط وتحته — كده الشعر الداكن أو اللحية
    # أو الكمامة الفاتحة مش هيتقروا كنظارة.
    skin_rows = skin_region_mask(region_bgr)
    skin_like = (skin_rows > 0) if skin_rows.size else np.zeros((height, 1), dtype=bool)
    if skin_like.shape[0] != height:
        skin_like = np.zeros((height, 1), dtype=bool)

    def _skin_between(start: int, end: int) -> float:
        if end <= start:
            return 0.0
        window = skin_like[max(0, start) : min(height, end)]
        return float(window.mean()) if window.size else 0.0

    best = 0
    run_start: int | None = None
    for i in range(len(band) + 1):
        is_glass = bool(band[i]) if i < len(band) else False
        if is_glass and run_start is None:
            run_start = i
        elif not is_glass and run_start is not None:
            run_length = i - run_start
            run_abs_start = top + run_start
            run_abs_end = top + i
            center = (run_abs_start + run_length / 2.0) / max(1, height)
            face_above = _skin_between(top, run_abs_start)
            face_below = _skin_between(run_abs_end, bottom)
            if (
                top > 0
                and i < len(band)
                and center <= GLASS_CENTER_MAX
                and face_above >= GLASS_MIN_FACE_SKIN
                and face_below >= GLASS_MIN_FACE_SKIN
            ):
                best = max(best, run_length)
            run_start = None

    ratio = best / float(max(1, height))
    if ratio < GLASS_BAND_MIN_ROWS or ratio > GLASS_BAND_MAX_ROWS:
        return 0.0
    return _clamp01(ratio)


def _eye_line_band(face_bgr: np.ndarray) -> tuple[int, int] | None:
    """
    خط العينين: أنسب شريط أفقي داكن في النص العلوي من الوش.

    بنستخدمه كبديل عن الـ cascade لما يكون مش متاح (OpenCV 5 مثلاً).
    """
    if not _is_usable(face_bgr, min_side=18):
        return None

    gray = cv2.equalizeHist(cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY))
    h, w = gray.shape[:2]
    upper = gray[: max(1, int(h * 0.7)), :]
    dark = (upper < DARK_V_MAX).astype(np.uint8)
    row_counts = dark.sum(axis=1)
    if row_counts.size == 0:
        return None
    peak = int(np.argmax(row_counts))
    if int(row_counts[peak]) < max(2, int(w * 0.05)):
        return None

    band_h = max(4, int(h * 0.10))
    y1 = max(0, peak - band_h // 2)
    y2 = min(h, y1 + band_h)
    if y2 - y1 < 3:
        return None
    return (y1, y2)


def _load_eye_cascade() -> cv2.CascadeClassifier | None:
    """
    تحميل مصنّف العين (اختياري).

    OpenCV 5 شال ``cv2.CascadeClassifier`` ومفاتيح haarcascades من الباكدج
    الرسمي، فبنتعامل مع ده بلطف: لو مش متاح بنستخدم كاشف العين الداخلي
    (``_dark_eye_candidates``) اللي شغال على التباين بدون أي ملفات خارجية.
    """
    global _EYE_CASCADE, _EYE_CASCADE_READY
    if _EYE_CASCADE_READY:
        return _EYE_CASCADE
    _EYE_CASCADE_READY = True

    _EYE_CASCADE = None
    if hasattr(cv2, "CascadeClassifier"):
        try:
            data_dir = getattr(cv2, "data", None)
            haarcascades = getattr(data_dir, "haarcascades", None) if data_dir else None
            if haarcascades:
                path = os.path.join(haarcascades, "haarcascade_eye.xml")
                if os.path.exists(path):
                    cascade = cv2.CascadeClassifier(path)
                    _EYE_CASCADE = None if cascade.empty() else cascade
        except Exception as exc:  # pragma: no cover - depends on cv2 build
            logger.debug("Eye cascade unavailable: %s", exc)
            _EYE_CASCADE = None

    if _EYE_CASCADE is None:
        logger.info("haarcascade eye detector unavailable; using built-in contrast eye/bridge detector")
    return _EYE_CASCADE


def find_eye_boxes(face_bgr: np.ndarray, *, max_faces: int = 6) -> list[Box]:
    """يكشف مستطيلات العينين داخل منطقة الوش (لو الـ cascade متاح)."""
    cascade = _load_eye_cascade()
    if cascade is None or not _is_usable(face_bgr, min_side=24):
        return []

    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    try:
        eyes = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(max(6, gray.shape[1] // 12), max(6, gray.shape[0] // 12)),
        )
    except cv2.error as exc:  # pragma: no cover - defensive
        logger.debug("Eye cascade failed: %s", exc)
        return []
    return [tuple(int(v) for v in eye) for eye in eyes[:max_faces]]


def _dark_eye_candidates(face_bgr: np.ndarray) -> list[Box]:
    """
    كاشف عينين بدون ملفات خارجية: عتبة أوتسو عكسية على النص العلوي من الوش،
    وبعدين نرشّح الكونتورات الدائرية نسبيًا (العين والحدقة داكنة، النظارة
    الواقية بتعمل شريط زجاجي فاتح/عاكس فبيقل عدد المرشحين).
    """
    if not _is_usable(face_bgr, min_side=18):
        return []

    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    h, w = gray.shape[:2]
    upper = gray[: max(1, int(h * 0.7)), :]

    try:
        _thr, binary = cv2.threshold(upper, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    except cv2.error:  # pragma: no cover - defensive
        return []

    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    contours = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = contours[0] if len(contours) == 2 else contours[1]

    area_total = float(max(1, upper.shape[0] * upper.shape[1]))
    candidates: list[Box] = []
    for contour in found:
        x, y, bw, bh = cv2.boundingRect(contour)
        if bw <= 1 or bh <= 1:
            continue
        area_ratio = (bw * bh) / area_total
        aspect = bw / float(bh)
        if area_ratio < 0.002 or area_ratio > 0.22:
            continue
        if aspect > 3.5 or aspect < 0.25:
            continue
        if bh > upper.shape[0] * 0.6:
            continue
        if y + bh / 2 < upper.shape[0] * 0.08:  # الحواجب/الشعر فوق خط العين
            continue
        candidates.append((int(x), int(y), int(bw), int(bh)))

    return sorted(candidates, key=lambda b: b[0])


def _pick_eye_pair(eyes: list[Box]) -> tuple[Box, Box] | None:
    """يختار أقرب عينين على نفس الخط الأفقي (يسار/يمين)."""
    if len(eyes) < 2:
        return None
    ordered = sorted(eyes, key=lambda e: e[0])
    best: tuple[Box, Box] | None = None
    best_score = -1.0
    for i in range(len(ordered) - 1):
        left, right = ordered[i], ordered[i + 1]
        avg_h = max(1.0, (left[3] + right[3]) / 2.0)
        gap = right[0] - (left[0] + left[2])
        vertical_offset = abs((left[1] + left[3] / 2) - (right[1] + right[3] / 2))
        if gap < 0 or vertical_offset > avg_h * 0.9:
            continue
        score = gap - vertical_offset
        if score > best_score:
            best_score = score
            best = (left, right)
    return best


def _bridge_box(left: Box, right: Box, shape: tuple[int, ...]) -> Box | None:
    """مستطيل جسر الأنف/ما بين العينين (أهم منطقة تحدد وجود النظارة)."""
    h, w = shape[:2]
    eye_h = max(left[3], right[3])
    x1 = left[0] + int(left[2] * 0.55)
    x2 = right[0] + int(right[2] * 0.40)
    y1 = max(left[1], right[1]) - int(eye_h * 0.15)
    y2 = min(left[1] + left[3], right[1] + right[3]) + int(eye_h * 0.25)
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    if x2 - x1 < 3 or y2 - y1 < 3:
        return None
    return (x1, y1, x2, y2)


def _fallback_bridge_box(shape: tuple[int, ...], band: tuple[int, int] | None = None) -> Box | None:
    """
    لو مالاقيناش عينين صريحة: نستخدم خط العينين المكتشف بالتباين (أو منتصف
    النص العلوي للوش كحل أخير) ونجيب الشريط الأوسط بينهم.
    """
    h, w = shape[:2]
    if h < 24 or w < 24:
        return None
    x1 = int(w * 0.35)
    x2 = int(w * 0.65)
    if band is not None:
        y1, y2 = band
    else:
        y1 = int(h * 0.28)
        y2 = int(h * 0.52)
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    if x2 - x1 < 3 or y2 - y1 < 3:
        return None
    return (x1, y1, x2, y2)


@dataclass(frozen=True)
class EyeBridgeResult:
    exposed: bool = False  # True => الوش مكشوف => بدون نظارات
    confidence: float = 0.0
    skin_ratio: float = 0.0
    dark_ratio: float = 0.0
    glass_ratio: float = 0.0
    eyes_found: int = 0
    bridge_box: Box | None = None

    @property
    def has_evidence(self) -> bool:
        return self.confidence > 0.0


def eye_bridge_exposed(
    face_bgr: np.ndarray,
    *,
    min_skin_ratio: float = 0.22,
) -> EyeBridgeResult:
    """
    اختبار جسر العينين لكشف ``NO-Goggles``.

    النظارة الواقية بتغطي منطقة ما بين العينين (جسر الأنف)، فلو الشريط اللي
    بين العينين جلد/عين مكشوفف بشكل واضح يبقى مفيش نظارة، والعكس: الشريط
    هيبقى زجاج (تشبع لون منخفض) أو معتم.
    """
    if not _is_usable(face_bgr, min_side=24):
        return EyeBridgeResult()

    # 1) مصنّف العين (لو متاح)  2) كاشف التباين الداخلي (شغال على OpenCV 5 برضه)
    eyes = find_eye_boxes(face_bgr)
    pair = _pick_eye_pair(eyes)
    if pair is None:
        eyes = _dark_eye_candidates(face_bgr)
        pair = _pick_eye_pair(eyes)

    glass_ratio = _glass_band_ratio(face_bgr)
    if glass_ratio >= GLASS_BAND_MIN_ROWS:
        # فيه شريط زجاجي/معتم على خط العينين => النظارة موجودة والوش مش مكشوف
        return EyeBridgeResult(
            exposed=False,
            confidence=0.0,
            glass_ratio=glass_ratio,
            eyes_found=len(eyes),
        )

    if pair is not None:
        box = _bridge_box(pair[0], pair[1], face_bgr.shape)
        softened = 1.0
        required_ratio = min_skin_ratio
    else:
        box = _fallback_bridge_box(face_bgr.shape, _eye_line_band(face_bgr))
        softened = 0.7  # بلا دليل عينين صريح => ثقة أقل + شرط جلد أقوى
        required_ratio = min_skin_ratio * 1.6

    if box is None:
        return EyeBridgeResult(eyes_found=len(eyes))

    x1, y1, x2, y2 = box
    strip = face_bgr[y1:y2, x1:x2]
    if not _is_usable(strip, min_side=3):
        return EyeBridgeResult(eyes_found=len(eyes), bridge_box=box)

    skin_ratio = calc_skin_ratio(strip)
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    dark_ratio = _clamp01(
        float(np.count_nonzero(hsv[:, :, 2] < DARK_V_MAX)) / max(1, strip.shape[0] * strip.shape[1])
    )

    exposed = skin_ratio >= required_ratio
    confidence = 0.0
    if exposed:
        upper = max(required_ratio * 1.5, min(0.8, required_ratio * 2.5))
        confidence = (0.45 + 0.50 * ratio_confidence(skin_ratio, required_ratio, upper)) * softened
        if dark_ratio > 0.05:
            # عين/حدقة ظاهرة في نفس الشريط = دليل إضافي إن الوش مكشوف
            confidence = min(0.95, confidence + 0.05)

    return EyeBridgeResult(
        exposed=bool(exposed),
        confidence=_clamp01(confidence),
        skin_ratio=skin_ratio,
        dark_ratio=dark_ratio,
        glass_ratio=glass_ratio,
        eyes_found=len(eyes),
        bridge_box=box,
    )


# ---------------------------------------------------------------------------
# Region geometry helpers (person box -> head / lower face / hand candidates)
# ---------------------------------------------------------------------------


def head_box(person_box: Box, ratio: float = 0.32) -> Box:
    """الجزء العلوي من مستطيل الشخص = منطقة الرأس/الوش."""
    x1, y1, x2, y2 = person_box
    height = max(1, y2 - y1)
    return (x1, y1, x2, y1 + max(1, int(height * ratio)))


def lower_face_box(head: Box, *, top: float = 0.45) -> Box:
    """أسفل الوش (الأنف والفم) = منطقة تحقق الكمامة."""
    x1, y1, x2, y2 = head
    height = max(1, y2 - y1)
    width = max(1, x2 - x1)
    return (
        x1 + int(width * 0.12),
        y1 + int(height * top),
        x2 - int(width * 0.12),
        y2,
    )


def hand_candidate_boxes(person_box: Box) -> list[Box]:
    """
    مناطق مرشحة لليدين داخل مستطيل الشخص (يمين/يسار منتصف الجسم + منطقة الوسط).

    تُستخدم لما الموديل ميبعتش أي بوكس قفازات، فنعمل مسح للجلد بأنفسنا.
    """
    x1, y1, x2, y2 = person_box
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    top = y1 + int(height * 0.35)
    bottom = y2

    side_w = max(8, int(width * 0.22))
    boxes: list[Box] = [
        (x1, top, x1 + side_w, bottom),
        (x2 - side_w, top, x2, bottom),
    ]
    center_half = max(8, int(width * 0.25))
    center_x = (x1 + x2) // 2
    boxes.append((center_x - center_half, y1 + int(height * 0.45), center_x + center_half, bottom))
    return boxes
