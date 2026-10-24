from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.camera.types import SOURCE_TYPES
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.model_policy import MODEL_FILENAME
from app.core.postprocess import NEAR_TIE_MARGIN, NEGATIVE_CLEAR_MARGIN
from app.core.ppe import PPE_CLASSES, canonical_class_name, ppe_meta, supported_negative_rules
from app.db.models import User

router = APIRouter(prefix="/meta", tags=["industrial configuration"])


def _model_meta(request: Request) -> dict:
    result = ppe_meta()
    names = getattr(getattr(request.app.state, "detector", None), "class_names", None)
    known = isinstance(names, dict | list)
    supported = supported_negative_rules(names) if known else None
    canonical = (
        {
            canonical_class_name(name)
            for name in (names.values() if isinstance(names, dict) else names)
        }
        if known
        else set()
    )
    result["capabilities_known"] = known
    result["supported_negative_rules"] = (
        [key for key in PPE_CLASSES if key in supported] if supported is not None else None
    )
    for rule in result["items"]:
        pair = PPE_CLASSES[rule["key"]]
        rule["negative_supported"] = rule["key"] in supported if known else None
        rule["positive_supported"] = pair["positive"] in canonical if known else None
    return result


@router.get("/ppe-classes")
def ppe_classes(request: Request, user: User = Depends(get_current_user)):
    return _model_meta(request)


@router.get("/system")
def system_meta(request: Request, user: User = Depends(get_current_user)):
    classes = _model_meta(request)
    return {
        "platform_name": "Mantik PPE",
        "scope": "industrial",
        "model": MODEL_FILENAME,
        "confidence": settings.DETECTION_CONFIDENCE,
        "negative_confidence": settings.DETECTION_NEGATIVE_CONFIDENCE,
        "effective_negative_confidence": max(
            settings.DETECTION_CONFIDENCE, settings.DETECTION_NEGATIVE_CONFIDENCE
        ),
        "capabilities_known": classes["capabilities_known"],
        "supported_negative_rules": classes["supported_negative_rules"],
        "conflict_policy": {
            "near_tie_margin": NEAR_TIE_MARGIN,
            "negative_clear_margin": NEGATIVE_CLEAR_MARGIN,
        },
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "max_video_seconds": settings.MAX_UPLOAD_VIDEO_SECONDS,
        "rules": classes["items"],
        "supported_source_types": list(SOURCE_TYPES),
        "recommended_source_type": "rtsp",
        "rtsp_sources_enabled": bool(settings.rtsp_prefixes),
        "http_sources_enabled": bool(settings.http_camera_prefixes),
        "file_sources_enabled": bool(settings.ALLOWED_VIDEO_DIR),
        "usb_sources_enabled": settings.APP_ENV == "dev" and settings.ENABLE_USB_SOURCES,
        "usb_device_indices": sorted(settings.usb_device_indices)
        if settings.APP_ENV == "dev" and settings.ENABLE_USB_SOURCES
        else [],
        "onvif_mode": "metadata_only",
    }
