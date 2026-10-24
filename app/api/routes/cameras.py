from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.camera.source_security import validate_camera_source
from app.core.auth import get_current_user, require_roles
from app.core.ppe import sanitize_enabled_classes
from app.core.rate_limit import get_client_ip
from app.db.audit import add_audit_event, hash_identifier
from app.db.models import Camera, Site, User
from app.db.session import get_db
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _redact_source_uri(source_type: str, source_uri: str) -> str:
    if source_type == "file":
        return "Restricted video file"
    parsed = urlsplit(source_uri)
    host = parsed.hostname or "configured camera"
    try:
        if parsed.port:
            host = f"{host}:{parsed.port}"
    except ValueError:
        pass
    return f"{parsed.scheme}://{host}/…"


def _to_response(cam: Camera, manager: CameraManager) -> CameraResponse:
    values = {
        field: getattr(cam, field) for field in CameraResponse.model_fields if field != "is_running"
    }
    values["source_uri"] = _redact_source_uri(cam.source_type, cam.source_uri)
    return CameraResponse(**values, is_running=manager.is_running(cam.id))


async def _validate_site(db: AsyncSession, site_id: int | None) -> None:
    if site_id is not None and await db.get(Site, site_id) is None:
        raise HTTPException(status_code=422, detail="Industrial site not found")


def _audit(
    request: Request,
    db: AsyncSession,
    action: str,
    user: User,
    camera: Camera,
    changed_fields: list[str] | None = None,
) -> None:
    details = {"site_id": camera.site_id, "source_type": camera.source_type}
    if changed_fields:
        details["changed_fields"] = changed_fields
    add_audit_event(
        db,
        action,
        actor_user_id=user.id,
        target_type="camera",
        target_id=camera.id,
        ip_hash=hash_identifier(get_client_ip(request)),
        details=details,
    )


@router.get("", response_model=list[CameraResponse])
async def list_cameras(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Camera)
    result = await db.execute(q)
    cameras = result.scalars().all()
    manager: CameraManager = get_camera_manager(request)
    return [_to_response(cam, manager) for cam in cameras]


@router.post("", response_model=CameraResponse, status_code=201)
async def create_camera(
    body: CameraCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "supervisor")),
):
    await _validate_site(db, body.site_id)
    try:
        source_uri = validate_camera_source(body.source_type, body.source_uri)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enabled = sanitize_enabled_classes(body.enabled_classes)
    cam = Camera(
        name=body.name.strip(),
        source_type=body.source_type,
        source_uri=source_uri,
        site_id=body.site_id,
        enabled_classes=enabled,
    )
    db.add(cam)
    await db.flush()
    _audit(request, db, "camera.created", user, cam)
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
    return _to_response(cam, get_camera_manager(request))


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "supervisor")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    changes: list[str] = []
    if "site_id" in body.model_fields_set:
        await _validate_site(db, body.site_id)
        cam.site_id = body.site_id
        changes.append("site_id")
    if body.name is not None:
        cam.name = body.name.strip()
        changes.append("name")
    if body.source_uri is not None:
        try:
            cam.source_uri = validate_camera_source(cam.source_type, body.source_uri)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        changes.append("source_uri")
    if body.enabled_classes is not None:
        cam.enabled_classes = sanitize_enabled_classes(body.enabled_classes)
        changes.append("enabled_classes")

    manager: CameraManager = get_camera_manager(request)
    if "source_uri" in changes:
        await manager.stop_camera(camera_id)
        cam.is_active = False
    # Record field names only; a changed source URI may contain camera credentials.
    _audit(request, db, "camera.updated", user, cam, changed_fields=changes)
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
    user: User = Depends(require_roles("admin", "supervisor")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)
    _audit(request, db, "camera.deleted", user, cam)
    await db.delete(cam)
    await db.commit()


@router.post("/{camera_id}/start")
async def start_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "supervisor")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    # Persist restart intent before processing starts. A short video may reach
    # EOF immediately; its worker must be the final writer of inactive state.
    cam.is_active = True
    await db.commit()
    try:
        ok = await manager.start_camera(
            camera_id,
            cam.source_type,
            cam.source_uri,
            cam.enabled_classes,
        )
    except (ValueError, asyncio.CancelledError) as exc:
        cam.is_active = False
        await db.commit()
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not ok:
        cam.is_active = False
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not open the camera source. Check the RTSP URI, network access, "
                "camera credentials and source availability."
            ),
        )

    _audit(request, db, "camera.started", user, cam)
    await db.commit()
    return {"status": "started", "camera_id": camera_id}


@router.post("/{camera_id}/stop")
async def stop_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "supervisor")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)
    cam.is_active = False
    _audit(request, db, "camera.stopped", user, cam)
    await db.commit()
    return {"status": "stopped", "camera_id": camera_id}
