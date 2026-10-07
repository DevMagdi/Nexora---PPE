from fastapi import APIRouter

from app.core.ppe import ALLOWED_PPE_KEYS, DEFAULT_ENABLED_CLASSES, PPE_LABELS

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/ppe-classes")
def ppe_classes():
    items = []
    for key in ALLOWED_PPE_KEYS:
        meta = PPE_LABELS.get(key, {"label_ar": key, "label_en": key})
        items.append({"key": key, **meta})

    return {
        "items": items,
        "default_enabled": DEFAULT_ENABLED_CLASSES,
        "allowed": ALLOWED_PPE_KEYS,
    }