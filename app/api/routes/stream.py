from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.core.config import settings
from app.core.logging import get_logger
from jose import jwt
from fastapi import Query, HTTPException
from app.core.config import settings
from app.db.models import User, Camera
from app.db.session import AsyncSessionLocal
from app.db.models import Camera, User
from app.db.session import AsyncSessionLocal

logger = get_logger(__name__)
router = APIRouter(tags=["stream"])


async def _mjpeg_generator(manager: CameraManager, camera_id: int):
    boundary = b"--frame"
    while True:
        frame = manager.get_latest_frame(camera_id)
        if frame:
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
async def mjpeg_stream(camera_id: int, request: Request, token: str = Query(default="")):
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        cam = await db.get(Camera, camera_id)
        if user is None or cam is None:
            raise HTTPException(status_code=401, detail="Invalid user/camera")
        if user.sector != "both" and cam.profile != user.sector:
            raise HTTPException(status_code=403, detail="Forbidden")

    manager: CameraManager = get_camera_manager(request)
    if not manager.is_running(camera_id):
        raise HTTPException(status_code=404, detail="Camera not running")

    return StreamingResponse(
        _mjpeg_generator(manager, camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.websocket("/ws/{camera_id}")
async def websocket_stream(websocket: WebSocket, camera_id: int, token: str = Query(default="")):
    await websocket.accept()
    manager: CameraManager = websocket.app.state.camera_manager

    if not manager.is_running(camera_id):
        await websocket.close(code=1008, reason="Camera not running")
        return

    # Auth token required
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    # validate token by calling /me logic (simple: decode by dependency style)
    # We'll reuse DB to fetch user and check sector.
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        cam = await db.get(Camera, camera_id)
        if user is None or cam is None:
            await websocket.close(code=1008, reason="Invalid user/camera")
            return
        if user.sector != "both" and cam.profile != user.sector:
            await websocket.close(code=1008, reason="Forbidden")
            return

    q = manager.subscribe(camera_id)
    try:
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=5.0)
                await websocket.send_text(json.dumps(data))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"ping": True}))
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        manager.unsubscribe(camera_id, q)