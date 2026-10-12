from __future__ import annotations

import re
from typing import Literal

Profile = Literal["construction", "medical"]

# ---------------------------------------------------------------------------
# Canonical class names
# ---------------------------------------------------------------------------
# The construction model emits CamelCase names (`NO-Goggles`) while the medical
# model emits lowercase ones (`no goggle`). The hybrid pipeline speaks a single
# canonical vocabulary so that `no goggle`, `no-goggle` and `NO-Goggles` are all
# the *same* class everywhere (checkers, merging, skin-heuristics output).
CANONICAL_CLASS_NAMES: tuple[str, ...] = (
    "Person",
    "Hardhat",
    "NO-Hardhat",
    "Safety Vest",
    "NO-Safety Vest",
    "Mask",
    "NO-Mask",
    "Gloves",
    "NO-Gloves",
    "Safety Boots",
    "NO-Safety Boots",
    "Goggles",
    "NO-Goggles",
    "Head Cap",
    "NO-Head Cap",
    "Lab Coat",
    "Full Cover",
    "Shoe Cover",
)

# صيغ بديلة بتظهر في الموديلات المختلفة (طبي lowercase / إنشائي CamelCase / اختصارات)
CLASS_NAME_ALIASES: dict[str, str] = {
    "person": "Person",
    "worker": "Person",
    "people": "Person",
    "hardhat": "Hardhat",
    "hard hat": "Hardhat",
    "helmet": "Hardhat",
    "no hardhat": "NO-Hardhat",
    "no hard hat": "NO-Hardhat",
    "no helmet": "NO-Hardhat",
    "safety vest": "Safety Vest",
    "vest": "Safety Vest",
    "safety-vest": "Safety Vest",
    "no safety vest": "NO-Safety Vest",
    "no vest": "NO-Safety Vest",
    "gloves": "Gloves",
    "glove": "Gloves",
    "hand gloves": "Gloves",
    "hand glove": "Gloves",
    "no gloves": "NO-Gloves",
    "no glove": "NO-Gloves",
    "no hand gloves": "NO-Gloves",
    "no hand glove": "NO-Gloves",
    "goggles": "Goggles",
    "goggle": "Goggles",
    "safety glasses": "Goggles",
    "eye protection": "Goggles",
    "no goggles": "NO-Goggles",
    "no goggle": "NO-Goggles",
    "no safety glasses": "NO-Goggles",
    "mask": "Mask",
    "face mask": "Mask",
    "facemask": "Mask",
    "no mask": "NO-Mask",
    "no face mask": "NO-Mask",
    "no facemask": "NO-Mask",
    "safety boots": "Safety Boots",
    "safety boot": "Safety Boots",
    "boots": "Safety Boots",
    "boot": "Safety Boots",
    "no safety boots": "NO-Safety Boots",
    "no boots": "NO-Safety Boots",
    "no boot": "NO-Safety Boots",
    "head cap": "Head Cap",
    "headcap": "Head Cap",
    "hair cap": "Head Cap",
    "hairnet": "Head Cap",
    "cap": "Head Cap",
    "no head cap": "NO-Head Cap",
    "no headcap": "NO-Head Cap",
    "no cap": "NO-Head Cap",
    "lab coat": "Lab Coat",
    "labcoat": "Lab Coat",
    "coat": "Lab Coat",
    "gown": "Lab Coat",
    "full cover": "Full Cover",
    "coverall": "Full Cover",
    "full body cover": "Full Cover",
    "shoe cover": "Shoe Cover",
    "shoe covers": "Shoe Cover",
    "boot cover": "Shoe Cover",
}

_KEY_SEP_RE = re.compile(r"[\s_\-]+")

CANONICAL_BY_KEY: dict[str, str] = {}


def class_key(name: str) -> str:
    """مفتاح موحّد للمقارنة: يتجاهل حالة الأحرف والمسافات والشرطات."""
    return _KEY_SEP_RE.sub(" ", (name or "").strip().lower())


for _alias, _canonical in CLASS_NAME_ALIASES.items():
    CANONICAL_BY_KEY[class_key(_alias)] = _canonical

for _name in CANONICAL_CLASS_NAMES:
    CANONICAL_BY_KEY[class_key(_name)] = _name


def canonical_class_name(name: str) -> str:
    """
    يحوّل أي صيغة اسم (طبية بحروف صغيرة أو إنشائية CamelCase) للاسم الموحّد.

    `no goggle` / `no-goggle` / `NO-Goggles`  ->  `NO-Goggles`
    """
    if not name:
        return ""
    return CANONICAL_BY_KEY.get(class_key(name), (name or "").strip())


def is_negative_class(name: str) -> bool:
    return canonical_class_name(name).startswith("NO-")

PPE_CLASS_MAPS: dict[Profile, dict[str, dict[str, str | None]]] = {
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
        # optional (no negative class in dataset — checked via absence when staff detected)
        "coat": {"label": "lab coat", "positive": "lab coat", "negative": None},
        "full_cover": {"label": "full cover", "positive": "full cover", "negative": None},
        "shoe_cover": {"label": "shoe cover", "positive": "shoe cover", "negative": None},
    },
}

# الصيغة الموحّدة لكل فئة (تُستخدم في الدمج الهجين وفلتر الجلد)
CANONICAL_MAP: dict[Profile, dict[str, dict[str, str | None]]] = {
    profile: {
        key: {
            "label": canonical_class_name(str(cfg.get("label") or key)),
            "positive": canonical_class_name(str(cfg["positive"])) if cfg.get("positive") else None,
            "negative": canonical_class_name(str(cfg["negative"])) if cfg.get("negative") else None,
        }
        for key, cfg in cfg_map.items()
    }
    for profile, cfg_map in PPE_CLASS_MAPS.items()
}

DEFAULT_ENABLED_BY_PROFILE: dict[Profile, list[str]] = {
    "construction": ["helmet", "vest"],
    "medical": ["mask", "gloves", "cap", "goggles"],
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


def sanitize_enabled_classes(profile: Profile, value: list[str] | None) -> list[str]:
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
