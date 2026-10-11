from __future__ import annotations

from typing import Optional, Literal

Profile = Literal["construction", "medical"]

PPE_CLASS_MAPS: dict[Profile, dict[str, dict[str, Optional[str]]]] = {
    "construction": {
        "helmet": {"label": "Hardhat", "positive": "Hardhat", "negative": "NO-Hardhat"},
        "vest": {"label": "Safety Vest", "positive": "Safety Vest", "negative": "NO-Safety Vest"},
        "mask": {"label": "Mask", "positive": "Mask", "negative": "NO-Mask"},
        "gloves": {"label": "Gloves", "positive": "Gloves", "negative": "NO-Gloves"},
        "boots": {"label": "Safety Boots", "positive": "Safety Boots", "negative": "NO-Safety Boots"},
        "goggles": {"label": "Goggles", "positive": "Goggles", "negative": "NO-Goggles"},
    },
    "medical": {
        # keys (UI/business) -> model class names (lowercase)
        "mask": {"label": "mask", "positive": "mask", "negative": "no mask"},
        "gloves": {"label": "hand gloves", "positive": "hand gloves", "negative": "no hand gloves"},
        "cap": {"label": "head cap", "positive": "head cap", "negative": "no head cap"},
        "goggles": {"label": "goggle", "positive": "goggle", "negative": "no goggle"},
        # optional (no negative class in dataset)
        "coat": {"label": "lab coat", "positive": "lab coat", "negative": None},
        "full_cover": {"label": "full cover", "positive": "full cover", "negative": None},
        "shoe_cover": {"label": "shoe cover", "positive": "shoe cover", "negative": None},
    },
}

DEFAULT_ENABLED_BY_PROFILE: dict[Profile, list[str]] = {
    "construction": ["helmet", "vest"],
    "medical": ["mask", "gloves", "cap"],
}

PPE_LABELS_BY_PROFILE: dict[Profile, dict[str, dict[str, str]]] = {
    "construction": {
        "helmet": {"label_ar": "خوذة", "label_en": "Helmet"},
        "vest": {"label_ar": "فيست / سيفتي", "label_en": "Safety Vest"},
        "mask": {"label_ar": "كمامة", "label_en": "Mask"},
        "gloves": {"label_ar": "جوانتي", "label_en": "Gloves"},
        "boots": {"label_ar": "حذاء أمان", "label_en": "Safety Boots"},
        "goggles": {"label_ar": "نظارات واقية", "label_en": "Goggles"},
    },
    "medical": {
        "mask": {"label_ar": "كمامة", "label_en": "Mask"},
        "gloves": {"label_ar": "جوانتي", "label_en": "Gloves"},
        "cap": {"label_ar": "كاب / غطاء رأس", "label_en": "Head Cap"},
        "goggles": {"label_ar": "نظارات واقية", "label_en": "Goggles"},
        "coat": {"label_ar": "بالطو", "label_en": "Lab Coat"},
        "full_cover": {"label_ar": "غطاء كامل", "label_en": "Full Cover"},
        "shoe_cover": {"label_ar": "غطاء حذاء", "label_en": "Shoe Cover"},
    },
}


def allowed_keys(profile: Profile) -> list[str]:
    return list(PPE_CLASS_MAPS[profile].keys())


def default_enabled(profile: Profile) -> list[str]:
    return DEFAULT_ENABLED_BY_PROFILE[profile].copy()


def sanitize_enabled_classes(profile: Profile, value: Optional[list[str]]) -> list[str]:
    """يرجع قائمة سليمة دائمًا، ولو None يرجع default."""
    if not value or not isinstance(value, list):
        return default_enabled(profile)

    allowed = set(allowed_keys(profile))
    cleaned = [v for v in value if isinstance(v, str) and v in allowed]
    return cleaned if cleaned else default_enabled(profile)


def ppe_meta(profile: Profile) -> dict:
    items = []
    labels = PPE_LABELS_BY_PROFILE.get(profile, {})
    for key in allowed_keys(profile):
        meta = labels.get(key, {"label_ar": key, "label_en": key})
        items.append({"key": key, **meta})
    return {
        "profile": profile,
        "items": items,
        "default_enabled": default_enabled(profile),
        "allowed": allowed_keys(profile),
    }