from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.core.auth import get_current_user
from app.core.ppe import sanitize_enabled_classes
from app.db.models import Camera, User
from app.db.session import get_db
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _to_response(cam: Camera, manager: CameraManager) -> CameraResponse:
    return CameraResponse(
        **{c: getattr(cam, c) for c in CameraResponse.model_fields if c != "is_running"},
        is_running=manager.is_running(cam.id),
    )


@router.get("", response_model=list[CameraResponse])
async def list_cameras(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Camera)
    if user.sector != "both":
        q = q.where(Camera.profile == user.sector)
    result = await db.execute(q)
    cameras = result.scalars().all()
    manager: CameraManager = get_camera_manager(request)
    return [_to_response(cam, manager) for cam in cameras]


@router.post("", response_model=CameraResponse, status_code=201)
async def create_camera(
    body: CameraCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # enforce profile based on user.sector
    if user.sector != "both":
        profile = user.sector
    else:
        profile = body.profile or "construction"

    enabled = sanitize_enabled_classes(profile, body.enabled_classes)

    cam = Camera(
        name=body.name,
        source_type=body.source_type,
        source_uri=body.source_uri,
        profile=profile,
        enabled_classes=enabled,
    )
    db.add(cam)
    await db.commit()
    await db.refresh(cam)

    manager: CameraManager = get_camera_manager(request)
    return _to_response(cam, manager)


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if user.sector != "both" and cam.profile != user.sector:
        raise HTTPException(status_code=403, detail="Forbidden")

    manager: CameraManager = get_camera_manager(request)
    return _to_response(cam, manager)


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if user.sector != "both" and cam.profile != user.sector:
        raise HTTPException(status_code=403, detail="Forbidden")

    if body.name is not None:
        cam.name = body.name
    if body.source_uri is not None:
        cam.source_uri = body.source_uri
    if body.enabled_classes is not None:
        cam.enabled_classes = sanitize_enabled_classes(cam.profile, body.enabled_classes)

    await db.commit()
    await db.refresh(cam)

    manager: CameraManager = get_camera_manager(request)
    manager.update_enabled_classes(camera_id, cam.enabled_classes)

    return _to_response(cam, manager)


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if user.sector != "both" and cam.profile != user.sector:
        raise HTTPException(status_code=403, detail="Forbidden")

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)

    await db.delete(cam)
    await db.commit()


@router.post("/{camera_id}/start")
async def start_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if user.sector != "both" and cam.profile != user.sector:
        raise HTTPException(status_code=403, detail="Forbidden")

    manager: CameraManager = get_camera_manager(request)

    try:
        ok = await manager.start_camera(camera_id, cam.profile, cam.source_type, cam.source_uri, cam.enabled_classes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ok:
        raise HTTPException(status_code=400, detail="Failed to start camera (check source URI)")

    cam.is_active = True
    await db.commit()
    return {"status": "started", "camera_id": camera_id}


@router.post("/{camera_id}/stop")
async def stop_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if user.sector != "both" and cam.profile != user.sector:
        raise HTTPException(status_code=403, detail="Forbidden")

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)

    cam.is_active = False
    await db.commit()
    return {"status": "stopped", "camera_id": camera_id}