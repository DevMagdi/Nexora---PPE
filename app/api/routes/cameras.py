from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.core.security import require_api_key
from app.db.models import Camera
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
):
    result = await db.execute(select(Camera))
    cameras = result.scalars().all()
    manager: CameraManager = get_camera_manager(request)
    return [_to_response(cam, manager) for cam in cameras]


@router.post(
    "",
    response_model=CameraResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def create_camera(
    body: CameraCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = Camera(
        name=body.name,
        source_type=body.source_type,
        source_uri=body.source_uri,
        enabled_classes=body.enabled_classes,
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
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    return _to_response(cam, manager)


@router.put(
    "/{camera_id}",
    response_model=CameraResponse,
    dependencies=[Depends(require_api_key)],
)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    if body.name is not None:
        cam.name = body.name
    if body.source_uri is not None:
        cam.source_uri = body.source_uri
    if body.enabled_classes is not None:
        cam.enabled_classes = body.enabled_classes

    await db.commit()
    await db.refresh(cam)

    manager: CameraManager = get_camera_manager(request)
    manager.update_enabled_classes(camera_id, cam.enabled_classes)

    return _to_response(cam, manager)


@router.delete("/{camera_id}", status_code=204, dependencies=[Depends(require_api_key)])
async def delete_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)

    await db.delete(cam)
    await db.commit()


@router.post("/{camera_id}/start", dependencies=[Depends(require_api_key)])
async def start_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)

    try:
        ok = await manager.start_camera(camera_id, cam.source_type, cam.source_uri, cam.enabled_classes)
    except ValueError as e:
        # بدل 500: رجّع 400 برسالة مفهومة
        raise HTTPException(status_code=400, detail=str(e))

    if not ok:
        raise HTTPException(status_code=400, detail="Failed to start camera (check source URI)")

    cam.is_active = True
    await db.commit()
    return {"status": "started", "camera_id": camera_id}


@router.post("/{camera_id}/stop", dependencies=[Depends(require_api_key)])
async def stop_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)

    cam.is_active = False
    await db.commit()
    return {"status": "stopped", "camera_id": camera_id}