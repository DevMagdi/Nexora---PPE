from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.model_policy import MODEL_FILENAME
from app.core.ppe import ppe_meta
from app.db.models import User

router = APIRouter(prefix="/meta", tags=["industrial configuration"])


@router.get("/ppe-classes")
def ppe_classes(user: User = Depends(get_current_user)):
    return ppe_meta()


@router.get("/system")
def system_meta(user: User = Depends(get_current_user)):
    return {
        "scope": "industrial",
        "model": MODEL_FILENAME,
        "confidence": settings.DETECTION_CONFIDENCE,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "max_video_seconds": settings.MAX_UPLOAD_VIDEO_SECONDS,
        "rules": ppe_meta()["items"],
    }
