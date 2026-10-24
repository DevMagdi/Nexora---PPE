from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.camera.source_security import (
    apply_network_credentials,
    validate_camera_source,
    validate_onvif_device_uri,
)
from app.camera.types import NETWORK_TYPES
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
    if source_type == "usb":
        return "Local development USB"
    parsed = urlsplit(source_uri)
    host = parsed.hostname or "configured camera"
    if ":" in host:
        host = f"[{host}]"
    try:
        if parsed.port:
            host = f"{host}:{parsed.port}"
    except ValueError:
        pass
    return f"{parsed.scheme}://{host}/…"


def _to_response(cam: Camera, manager: CameraManager) -> CameraResponse:
    values = {
        field: getattr(cam, field)
        for field in CameraResponse.model_fields
        if field not in {"is_running", "connection_status", "port"}
    }
    values["source_uri"] = _redact_source_uri(cam.source_type, cam.source_uri)
    status = manager.get_connection_status(cam.id)
    error = manager.get_last_error(cam.id)
    running = manager.is_running(cam.id)
    if running:
        status, error = "running", None
    elif status == "running":
        status, error = "retrying", "بانتظار إطار فيديو حديث؛ راجع حالة الاتصال."
    if status == "stopped" and cam.last_error:
        status, error = "error", cam.last_error
    values["last_error"] = error
    values["port"] = urlsplit(cam.source_uri).port if cam.source_type in NETWORK_TYPES else None
    return CameraResponse(**values, is_running=running, connection_status=status)


_SOURCE_FIELDS = {
    "source_type",
    "source_uri",
    "device_index",
    "port",
    "source_username",
    "source_password",
    "clear_credentials",
    "auth_mode",
    "onvif_device_uri",
}


def _source_values(body: CameraCreate | CameraUpdate, existing: Camera | None = None) -> dict:
    kind = body.source_type or (existing.source_type if existing else None)
    changed_type = existing is not None and kind != existing.source_type
    network = kind in NETWORK_TYPES
    uri = (
        body.source_uri
        if body.source_uri is not None
        else existing.source_uri
        if existing and not changed_type
        else ""
    )
    index = (
        body.device_index
        if body.device_index is not None
        else existing.device_index
        if existing and not changed_type
        else None
    )
    auth_mode = body.auth_mode or (
        existing.auth_mode if existing and network and not changed_type else "basic"
    )
    onvif = body.onvif_device_uri
    if (
        isinstance(body, CameraUpdate)
        and "onvif_device_uri" not in body.model_fields_set
        and existing
        and network
        and not changed_type
    ):
        onvif = existing.onvif_device_uri
    if not network:
        if (
            body.port is not None
            or body.source_username is not None
            or body.source_password is not None
            or body.clear_credentials
            or onvif
            or auth_mode != "basic"
        ):
            raise ValueError("Network/authentication fields are not valid for file/USB sources")
        auth_mode, onvif = "basic", None
    else:
        if body.device_index is not None:
            raise ValueError("Device index is only valid for USB")
        index = None
        if kind in {"rtsp", "rtsps"} and auth_mode != "basic":
            raise ValueError(
                "HTTP auth_mode is only valid for HTTP MJPEG/HLS; RTSP negotiates camera authentication automatically"
            )
        if body.clear_credentials and (
            body.source_username is not None or body.source_password is not None
        ):
            raise ValueError("Do not replace and clear credentials in the same request")
        uri = apply_network_credentials(
            uri,
            port=body.port,
            username=body.source_username,
            password=body.source_password.get_secret_value()
            if body.source_password is not None
            else None,
            clear=body.clear_credentials,
            replace_port=existing is not None and body.source_uri is None,
        )
    if kind == "usb" and body.source_uri is not None:
        raise ValueError("USB does not accept a source URI")
    if kind != "usb" and body.device_index is not None:
        raise ValueError("Device index is only valid for USB")
    uri = validate_camera_source(kind, uri, device_index=index)
    onvif = validate_onvif_device_uri(onvif, kind) if network else None
    return {
        "source_type": kind,
        "source_uri": uri,
        "device_index": index if kind == "usb" else None,
        "auth_mode": auth_mode,
        "onvif_device_uri": onvif,
    }


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
        source_values = _source_values(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enabled = sanitize_enabled_classes(body.enabled_classes)
    cam = Camera(
        name=body.name.strip(),
        **source_values,
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
    source_changes = _SOURCE_FIELDS.intersection(body.model_fields_set)
    if source_changes:
        try:
            values = _source_values(body, cam)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        for field, value in values.items():
            setattr(cam, field, value)
        changes.extend(sorted(source_changes))
    if body.enabled_classes is not None:
        cam.enabled_classes = sanitize_enabled_classes(body.enabled_classes)
        changes.append("enabled_classes")

    manager: CameraManager = get_camera_manager(request)
    if source_changes:
        await manager.stop_camera(camera_id)
        cam.is_active = False
        cam.last_error = None
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
    cam.last_error = None
    await db.commit()
    try:
        ok = await manager.start_camera(
            camera_id,
            cam.source_type,
            cam.source_uri,
            cam.enabled_classes,
            **({"auth_mode": cam.auth_mode} if cam.auth_mode != "basic" else {}),
        )
    except (ValueError, asyncio.CancelledError) as exc:
        cam.is_active = False
        if isinstance(exc, asyncio.CancelledError):
            await db.commit()
            raise
        # Native exceptions may contain credential-bearing URLs. Return only our safe status.
        cam.last_error = (
            manager.get_last_error(camera_id)
            or "تعذّر تشغيل الكاميرا؛ راجع المصدر والصلاحيات وسياسة الشبكة."
        )
        await db.commit()
        raise HTTPException(status_code=400, detail=cam.last_error) from None

    if not ok:
        cam.is_active = False
        cam.last_error = (
            manager.get_last_error(camera_id)
            or "تعذّر فتح المصدر؛ راجع العنوان والمصادقة وتوفّر الفيديو."
        )
        await db.commit()
        raise HTTPException(status_code=400, detail=cam.last_error)

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
    cam.last_error = None
    _audit(request, db, "camera.stopped", user, cam)
    await db.commit()
    return {"status": "stopped", "camera_id": camera_id}
