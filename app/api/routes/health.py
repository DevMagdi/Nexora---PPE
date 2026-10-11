from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    try:
        manager: CameraManager = get_camera_manager(request)
        active = manager.active_count()
        detectors_loaded = hasattr(request.app.state, "detectors")
    except Exception:
        active = 0
        detectors_loaded = False

    return {
        "status": "ok",
        "detectors_loaded": detectors_loaded,
        "cameras_active": active,
    }