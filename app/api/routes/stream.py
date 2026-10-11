from __future__ import annotations

import asyncio
import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.core.auth import decode_token_user_id, get_current_user_media
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Camera, User
from app.db.session import AsyncSessionLocal, get_db

logger = get_logger(__name__)
router = APIRouter(tags=["stream"])


async def _mjpeg_generator(manager: CameraManager, camera_id: int, request: Request):
    boundary = b"--frame"
    last_seq = -1
    while manager.is_running(camera_id):
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
        raise HTTPException(status_code=403, detail="Forbidden")

    manager: CameraManager = get_camera_manager(request)
    if not manager.is_running(camera_id):
        raise HTTPException(status_code=404, detail="Camera not running")

    return StreamingResponse(
        _mjpeg_generator(manager, camera_id, request),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.websocket("/ws/{camera_id}")
async def websocket_stream(
    websocket: WebSocket,
    camera_id: int,
    token: str = Query(default=""),
):
    await websocket.accept()
    manager: CameraManager = websocket.app.state.camera_manager

    if not manager.is_running(camera_id):
        await websocket.close(code=1008, reason="Camera not running")
        return

    try:
        user_id = decode_token_user_id(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid or missing token")
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
        initial_counts = manager.get_latest_counts(camera_id)
        if initial_counts:
            await websocket.send_text(json.dumps(initial_counts))

        while manager.is_running(camera_id):
            try:
                data = await asyncio.wait_for(q.get(), timeout=5.0)
                await websocket.send_text(json.dumps(data))
            except TimeoutError:
                await websocket.send_text(json.dumps({"ping": True}))
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        manager.unsubscribe(camera_id, q)
