from __future__ import annotations

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
from app.db.models import Camera, User
from app.db.session import get_db
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _redact_source_uri(source_type: str, source_uri: str) -> str:
    if source_type == "webcam":
        return "Webcam"
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
    values = {field: getattr(cam, field) for field in CameraResponse.model_fields if field != "is_running"}
    values["source_uri"] = _redact_source_uri(cam.source_type, cam.source_uri)
    return CameraResponse(**values, is_running=manager.is_running(cam.id))


def _check_sector_access(user: User, camera: Camera) -> None:
    if user.sector != "both" and camera.profile != user.sector:
        raise HTTPException(status_code=403, detail="Forbidden")


def _audit(
    request: Request,
    db: AsyncSession,
    action: str,
    user: User,
    camera: Camera,
    changed_fields: list[str] | None = None,
) -> None:
    details = {"profile": camera.profile, "source_type": camera.source_type}
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
    user: User = Depends(require_roles("admin", "operator")),
):
    profile = user.sector if user.sector != "both" else body.profile or "construction"
    if user.sector != "both" and body.profile not in (None, user.sector):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        source_uri = validate_camera_source(body.source_type, body.source_uri)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enabled = sanitize_enabled_classes(profile, body.enabled_classes)  # type: ignore[arg-type]
    cam = Camera(
        name=body.name.strip(),
        source_type=body.source_type,
        source_uri=source_uri,
        profile=profile,
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
    _check_sector_access(user, cam)
    return _to_response(cam, get_camera_manager(request))


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    _check_sector_access(user, cam)

    changes: list[str] = []
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
        cam.enabled_classes = sanitize_enabled_classes(cam.profile, body.enabled_classes)  # type: ignore[arg-type]
        changes.append("enabled_classes")

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
    user: User = Depends(require_roles("admin", "operator")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    _check_sector_access(user, cam)

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
    user: User = Depends(require_roles("admin", "operator")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    _check_sector_access(user, cam)

    manager: CameraManager = get_camera_manager(request)
    try:
        ok = await manager.start_camera(
            camera_id,
            cam.profile,  # type: ignore[arg-type]
            cam.source_type,
            cam.source_uri,
            cam.enabled_classes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not ok:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not open the camera source. Check the URI or webcam index, operating-system "
                "camera permissions, and whether another app is using the device. If the backend "
                "runs in Docker, expose the host camera to the container."
            ),
        )

    cam.is_active = True
    _audit(request, db, "camera.started", user, cam)
    await db.commit()
    return {"status": "started", "camera_id": camera_id}


@router.post("/{camera_id}/stop")
async def stop_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    _check_sector_access(user, cam)

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)
    cam.is_active = False
    _audit(request, db, "camera.stopped", user, cam)
    await db.commit()
    return {"status": "stopped", "camera_id": camera_id}
