from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import math
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.api.routes.cameras import _to_response, _validate_site
from app.camera.source_security import validate_file_uri
from app.core.auth import require_roles
from app.core.config import settings
from app.core.frame_annotator import annotate_frame
from app.core.ppe import display_classes, sanitize_enabled_classes
from app.db.audit import add_audit_event
from app.db.models import Camera, User
from app.db.session import get_db
from app.schemas.camera import CameraResponse

router = APIRouter(prefix="/inference", tags=["industrial inference"])


def _rules(value: str) -> list[str]:
    try:
        return sanitize_enabled_classes([part.strip() for part in value.split(",") if part.strip()])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _image_bytes(upload: UploadFile) -> bytes:
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = bytearray()
    try:
        while chunk := await upload.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > limit:
                raise HTTPException(
                    status_code=413, detail="Upload exceeds the configured size limit"
                )
    finally:
        await upload.close()
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded image is empty")
    return bytes(data)


def _decode_image(data: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG"}:
                raise ValueError("Only JPEG and PNG images are supported")
            width, height = image.size
            if width * height > settings.MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions exceed the configured pixel limit")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=422, detail="Invalid or oversized JPEG/PNG image") from exc
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=422, detail="Image cannot be decoded")
    return frame


@router.post("/image")
async def infer_image(
    request: Request,
    file: UploadFile = File(...),
    enabled_classes: str = Form(default="helmet,vest"),
    user: User = Depends(require_roles("admin", "supervisor")),
):
    raw_rules = (await request.form()).get("enabled_classes")
    rules = _rules(raw_rules if isinstance(raw_rules, str) else enabled_classes)
    data = await _image_bytes(file)
    frame = await asyncio.to_thread(_decode_image, data)
    async with request.app.state.inference_slots:
        detections = await asyncio.to_thread(request.app.state.detector.detect, frame)
    allowed = display_classes(rules)
    detections = [d for d in detections if d.class_name in allowed]
    annotated = await asyncio.to_thread(annotate_frame, frame, detections, [])
    scale = min(1.0, 1600 / max(annotated.shape[:2]))
    if scale < 1:
        annotated = cv2.resize(annotated, None, fx=scale, fy=scale)
    ok, jpeg = await asyncio.to_thread(cv2.imencode, ".jpg", annotated)
    if not ok:
        raise HTTPException(status_code=422, detail="Image preview could not be encoded")
    return {
        "detections": [
            {
                "class_name": d.class_name,
                "confidence": d.confidence,
                "box": [d.x1, d.y1, d.x2, d.y2],
            }
            for d in detections
        ],
        "preview": "data:image/jpeg;base64," + base64.b64encode(jpeg.tobytes()).decode("ascii"),
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
    }


def _validate_video(path: Path) -> None:
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if (
            not cap.isOpened()
            or not math.isfinite(fps)
            or fps <= 0
            or not math.isfinite(frame_count)
            or frame_count <= 0
        ):
            raise ValueError("Video has no readable duration or frames")
        if frame_count / fps > settings.MAX_UPLOAD_VIDEO_SECONDS:
            raise ValueError("Video exceeds the configured duration limit")
        width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if not math.isfinite(width * height) or width * height > settings.MAX_IMAGE_PIXELS:
            raise ValueError("Video resolution exceeds the configured pixel limit")
        ok, frame = cap.read()
        if not ok or frame is None:
            raise ValueError("Video has no decodable frame")
    finally:
        cap.release()


@router.post("/video", response_model=CameraResponse, status_code=201)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(min_length=1, max_length=100),
    site_id: int | None = Form(default=None, gt=0),
    enabled_classes: str = Form(default="helmet,vest"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "supervisor")),
):
    raw_rules = (await request.form()).get("enabled_classes")
    rules = _rules(raw_rules if isinstance(raw_rules, str) else enabled_classes)
    await _validate_site(db, site_id)
    if not name.strip():
        raise HTTPException(status_code=422, detail="Video source name is required")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".avi"}:
        raise HTTPException(status_code=422, detail="Only MP4 and AVI videos are supported")
    root = Path(settings.UPLOADS_DIR).resolve()
    base = Path(settings.ALLOWED_VIDEO_DIR).resolve() if settings.ALLOWED_VIDEO_DIR else None
    if base is None or not root.is_relative_to(base):
        raise HTTPException(
            status_code=503,
            detail="Configure UPLOADS_DIR inside ALLOWED_VIDEO_DIR before uploading video",
        )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / (uuid.uuid4().hex + suffix)
    size = 0
    committed = False
    try:
        # Original filenames are never used as paths; incomplete uploads are removed.
        with path.open("xb") as handle:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=413, detail="Upload exceeds the configured size limit"
                    )
                await asyncio.to_thread(handle.write, chunk)
        if not size:
            raise ValueError("The uploaded video is empty")
        await asyncio.to_thread(_validate_video, path)
        uri = validate_file_uri(str(path))
        camera = Camera(
            name=name.strip(),
            source_type="file",
            source_uri=uri,
            site_id=site_id,
            enabled_classes=rules,
        )
        db.add(camera)
        await db.flush()
        add_audit_event(
            db,
            "camera.video_uploaded",
            actor_user_id=user.id,
            target_type="camera",
            target_id=camera.id,
        )
        await db.commit()
        committed = True
        await db.refresh(camera)
        return _to_response(camera, get_camera_manager(request))
    except BaseException as exc:
        # Never orphan a committed camera by removing its video on a later
        # response/refresh failure. Only roll back and remove uncommitted uploads.
        if not committed:
            with contextlib.suppress(Exception):
                await db.rollback()
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise
    finally:
        await file.close()
