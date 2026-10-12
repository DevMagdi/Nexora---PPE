from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.core.auth import decode_token_payload, get_current_user_media, media_cookie_name
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Camera, User
from app.db.session import AsyncSessionLocal, get_db

logger = get_logger(__name__)
router = APIRouter(tags=["stream"])
MEDIA_SESSION_REVALIDATE_SECONDS = 5.0


async def _media_session_is_current(user_id: int, token_version: int) -> bool:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        return bool(
            user is not None
            and user.is_active
            and not user.must_change_password
            and user.token_version == token_version
        )


async def _mjpeg_generator(
    manager: CameraManager,
    camera_id: int,
    request: Request,
    user_id: int,
    token_version: int,
):
    boundary = b"--frame"
    last_seq = -1
    media_expires_at = getattr(request.state, "media_expires_at", None)
    last_session_check = time.monotonic()
    while manager.is_running(camera_id):
        if media_expires_at and datetime.now(UTC) >= media_expires_at:
            break
        if time.monotonic() - last_session_check >= MEDIA_SESSION_REVALIDATE_SECONDS:
            if not await _media_session_is_current(user_id, token_version):
                break
            last_session_check = time.monotonic()
        if await request.is_disconnected():
            break
        frame, seq = manager.get_latest_frame_with_seq(camera_id)
        if frame and seq != last_seq:
            last_seq = seq
            yield (
                boundary
                + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(frame)).encode()
                + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )
        await asyncio.sleep(settings.STREAM_FPS_DELAY_SECONDS)


@router.get("/stream/{camera_id}")
async def mjpeg_stream(
    camera_id: int,
    request: Request,
    user: User = Depends(get_current_user_media),
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if user.sector != "both" and cam.profile != user.sector:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    if not manager.is_running(camera_id):
        raise HTTPException(status_code=404, detail="Camera not running")

    return StreamingResponse(
        _mjpeg_generator(manager, camera_id, request, user.id, user.token_version),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "private, no-store",
            "X-Accel-Buffering": "no",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.websocket("/ws/{camera_id}")
async def websocket_stream(websocket: WebSocket, camera_id: int):
    if (
        settings.APP_ENV == "prod"
        and websocket.url.scheme != "wss"
        and websocket.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower() != "https"
    ):
        await websocket.close(code=1008, reason="Secure WebSocket required")
        return

    origin = websocket.headers.get("origin")
    if origin and origin.rstrip("/") not in settings.cors_origins:
        await websocket.close(code=1008, reason="Untrusted origin")
        return

    # Browsers attach HttpOnly cookies automatically. Never accept a token from
    # the query string: URLs are commonly copied to browser/proxy access logs.
    token = websocket.cookies.get(media_cookie_name(), "")
    try:
        payload = decode_token_payload(token, expected_type="media")
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid or missing media session")
        return

    async with AsyncSessionLocal() as db:
        user = await db.get(User, int(payload["sub"]))
        cam = await db.get(Camera, camera_id)
        if (
            user is None
            or not user.is_active
            or user.must_change_password
            or user.token_version != int(payload.get("ver", 0))
            or cam is None
        ):
            await websocket.close(code=1008, reason="Invalid session or camera")
            return
        if user.sector != "both" and cam.profile != user.sector:
            await websocket.close(code=1008, reason="Forbidden")
            return

    manager: CameraManager = websocket.app.state.camera_manager
    if not manager.is_running(camera_id):
        await websocket.close(code=1008, reason="Camera not running")
        return

    media_expires_at = datetime.fromtimestamp(float(payload["exp"]), UTC)
    token_version = int(payload.get("ver", 0))
    last_session_check = time.monotonic()
    # Authentication, activity, token version, camera existence, sector, and
    # camera state are checked before the WebSocket handshake is accepted.
    await websocket.accept()
    q = manager.subscribe(camera_id)
    close_reason: str | None = None
    try:
        initial_counts = manager.get_latest_counts(camera_id)
        if initial_counts:
            await websocket.send_text(json.dumps(initial_counts))

        while manager.is_running(camera_id) and datetime.now(UTC) < media_expires_at:
            if time.monotonic() - last_session_check >= MEDIA_SESSION_REVALIDATE_SECONDS:
                if not await _media_session_is_current(user.id, token_version):
                    close_reason = "Media session revoked"
                    break
                last_session_check = time.monotonic()
            try:
                data = await asyncio.wait_for(q.get(), timeout=5.0)
                await websocket.send_text(json.dumps(data))
            except TimeoutError:
                await websocket.send_text(json.dumps({"ping": True}))
        if datetime.now(UTC) >= media_expires_at:
            close_reason = "Media session expired"
        if close_reason:
            await websocket.close(code=1008, reason=close_reason)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("WebSocket stream ended unexpectedly for camera_id=%s", camera_id)
    finally:
        manager.unsubscribe(camera_id, q)
