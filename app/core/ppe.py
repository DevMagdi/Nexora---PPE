from __future__ import annotations

import re

# The complete, closed industrial vocabulary used by inference, APIs and workers.
CANONICAL_CLASS_NAMES: tuple[str, ...] = (
    "Person",
    "Hardhat",
    "NO-Hardhat",
    "Safety Vest",
    "NO-Safety Vest",
    "Gloves",
    "NO-Gloves",
    "Safety Boots",
    "NO-Boot",
    "Goggles",
    "NO-Goggles",
)

_SEPARATOR = re.compile(r"[\s_-]+")


def class_key(name: str) -> str:
    return _SEPARATOR.sub(" ", str(name or "").strip().casefold())

_ALIASES: dict[str, tuple[str, ...]] = {
    "Person": ("worker", "people", "person"),
    "Hardhat": ("hard hat", "helmet", "safety helmet", "hardhat"),
    "NO-Hardhat": ("no hard hat", "no helmet", "no safety helmet", "no_helmet", "no-helmet"),
    "Safety Vest": ("vest", "safetyvest", "safety vest"),
    "NO-Safety Vest": ("no vest", "no safetyvest", "no_vest", "no-vest", "no safety vest"),
    "Gloves": ("glove", "hand gloves", "hand glove", "safety gloves"),
    "NO-Gloves": ("no glove", "no hand gloves", "no hand glove", "no safety gloves", "no_gloves", "no-gloves"),
    "Safety Boots": ("boot", "boots", "safety boot", "safety boots", "safety shoes"),
    "NO-Boot": ("no boot", "no boots", "no safety boot", "no safety boots", "no safety shoes", "no_boot", "no-boots", "no_boots"),
    "Goggles": ("goggle", "safety glasses", "eye protection"),
    "NO-Goggles": ("no goggle", "no safety glasses", "no eye protection", "no_goggles", "no-goggles"),
}
CANONICAL_BY_KEY = {
    class_key(alias): canonical
    for canonical, aliases in _ALIASES.items()
    for alias in (canonical, *aliases)
}


def canonical_class_name(name: str) -> str:
    """Unknown classes never enter the industrial vocabulary."""
    return CANONICAL_BY_KEY.get(class_key(name), "")


def is_negative_class(name: str) -> bool:
    return canonical_class_name(name).startswith("NO-")


PPE_CLASSES: dict[str, dict[str, str]] = {
    "helmet": {
        "positive": "Hardhat",
        "negative": "NO-Hardhat",
        "label_ar": "خوذة أمان",
        "label_en": "Hardhat",
    },
    "vest": {
        "positive": "Safety Vest",
        "negative": "NO-Safety Vest",
        "label_ar": "سترة عاكسة",
        "label_en": "Safety Vest",
    },
    "gloves": {
        "positive": "Gloves",
        "negative": "NO-Gloves",
        "label_ar": "قفازات عمل",
        "label_en": "Gloves",
    },
    "boots": {
        "positive": "Safety Boots",
        "negative": "NO-Boot",
        "label_ar": "حذاء أمان",
        "label_en": "Safety Boots",
    },
    "goggles": {
        "positive": "Goggles",
        "negative": "NO-Goggles",
        "label_ar": "نظارات واقية",
        "label_en": "Goggles",
    },
}
DEFAULT_ENABLED = ("helmet", "vest")


def default_enabled() -> list[str]:
    return list(DEFAULT_ENABLED)


def sanitize_enabled_classes(value: list[str] | None) -> list[str]:
    if value is None:
        return default_enabled()
    if not isinstance(value, list) or not value:
        raise ValueError("Select at least one industrial PPE rule")
    if any(not isinstance(key, str) or key not in PPE_CLASSES for key in value):
        raise ValueError("Unsupported PPE rule; use helmet, vest, gloves, boots or goggles")
    return list(dict.fromkeys(value))


def display_classes(enabled: list[str]) -> set[str]:
    names = {"Person"}
    for key in sanitize_enabled_classes(enabled):
        names.update((PPE_CLASSES[key]["positive"], PPE_CLASSES[key]["negative"]))
    return names


def ppe_meta() -> dict:
    return {
        "scope": "industrial",
        "items": [
            {"key": key, "label_ar": cfg["label_ar"], "label_en": cfg["label_en"]}
            for key, cfg in PPE_CLASSES.items()
        ],
        "default_enabled": default_enabled(),
        "allowed": list(PPE_CLASSES),
        "classes": list(CANONICAL_CLASS_NAMES),
    }
