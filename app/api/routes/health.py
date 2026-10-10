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
        model_loaded = hasattr(request.app.state, "detector")
    except Exception:
        active = 0
        model_loaded = False

    return {
        "status": "ok",
        "model_loaded": model_loaded,
        "cameras_active": active,
    }


@router.get("/metrics")
async def metrics(request: Request):
    try:
        manager: CameraManager = get_camera_manager(request)
        counts_by_camera = manager.counts_snapshot()
    except Exception:
        counts_by_camera = {}

    return {
        "cameras": counts_by_camera,
    }