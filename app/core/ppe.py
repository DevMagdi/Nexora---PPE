from __future__ import annotations

from typing import Optional

# مفاتيح Nexora اللي المستخدم هيختار منها
# وربطها بأسماء كلاسّات الموديل (Ultralytics YOLO)
PPE_CLASS_MAP: dict[str, dict[str, Optional[str]]] = {
    "helmet": {"label": "Hardhat", "positive": "Hardhat", "negative": "NO-Hardhat"},
    "vest": {"label": "Safety Vest", "positive": "Safety Vest", "negative": "NO-Safety Vest"},
    "mask": {"label": "Mask", "positive": "Mask", "negative": "NO-Mask"},

    # Coming soon (الموديل الحالي غالبًا لا يدعمهم)
    "gloves": {"label": "Gloves", "positive": "Gloves", "negative": "NO-Gloves"},
    "boots": {"label": "Safety Boots", "positive": "Safety Boots", "negative": "NO-Safety Boots"},
    "goggles": {"label": "Goggles", "positive": "Goggles", "negative": "NO-Goggles"},
}

ALLOWED_PPE_KEYS: list[str] = list(PPE_CLASS_MAP.keys())

# default لأي كاميرا جديدة
DEFAULT_ENABLED_CLASSES: list[str] = ["helmet", "vest"]

# Labels للواجهة
PPE_LABELS: dict[str, dict[str, str]] = {
    "helmet": {"label_ar": "خوذة", "label_en": "Helmet"},
    "vest": {"label_ar": "فيست / سيفتي", "label_en": "Safety Vest"},
    "mask": {"label_ar": "كمامة", "label_en": "Mask"},
    "gloves": {"label_ar": "جوانتي", "label_en": "Gloves"},
    "boots": {"label_ar": "حذاء واقي", "label_en": "Safety Boots"},
    "goggles": {"label_ar": "نظارات واقية", "label_en": "Goggles"},
    #"coat": {"label_ar": "بالطو / أوفرول", "label_en": "Lab Coat / Coverall"},
}


def sanitize_enabled_classes(value: Optional[list[str]]) -> list[str]:
    """يرجع قائمة سليمة دائمًا، ولو None يرجع default."""
    if not value or not isinstance(value, list):
        return DEFAULT_ENABLED_CLASSES.copy()

    cleaned = [v for v in value if isinstance(v, str) and v in PPE_CLASS_MAP]
    return cleaned if cleaned else DEFAULT_ENABLED_CLASSES.copy()