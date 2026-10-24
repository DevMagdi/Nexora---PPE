from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.core.auth import require_roles
from app.db.models import User

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    # Keep this endpoint suitable for a reverse-proxy liveness probe: do not
    # disclose model state, database details, paths, versions, or camera counts.
    return {"status": "ok"}


@router.get("/metrics")
async def metrics(
    request: Request,
    user: User = Depends(require_roles("admin")),
):
    manager: CameraManager = get_camera_manager(request)
    return {
        "cameras_active": manager.active_count(),
        "cameras": manager.counts_snapshot(),
    }
