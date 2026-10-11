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
        detectors_loaded = bool(
            getattr(request.app.state, "detectors", None)
            or getattr(request.app.state, "detector", None)
        )
    except Exception:
        active = 0
        detectors_loaded = False

    return {
        "status": "ok",
        "detectors_loaded": detectors_loaded,
        "model_loaded": detectors_loaded,
        "cameras_active": active,
    }


@router.get("/metrics")
async def metrics(request: Request):
    try:
        manager: CameraManager = get_camera_manager(request)
        cameras = manager.counts_snapshot()
        active = manager.active_count()
    except Exception:
        cameras = {}
        active = 0

    return {
        "cameras_active": active,
        "cameras": cameras,
    }
