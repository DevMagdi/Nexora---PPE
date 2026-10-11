from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field

import cv2

from app.alerts.base import AlertHandler
from app.alerts.dispatcher import AlertDispatcher
from app.alerts.email_handler import EmailHandler
from app.alerts.webhook_handler import WebhookHandler
from app.camera.source import CameraSource
from app.core.config import settings
from app.core.detector import PPEDetector
from app.core.frame_annotator import annotate_frame
from app.core.logging import get_logger
from app.core.ppe import sanitize_enabled_classes, Profile
from app.core.violation_checker import ConstructionViolationChecker, MedicalViolationChecker, BaseViolationChecker
from app.db.repository import record_alert_log, save_violation

logger = get_logger(__name__)


@dataclass
class _CameraEntry:
    camera_id: int
    profile: Profile
    source: CameraSource
    enabled_classes: list[str] = field(default_factory=list)
    task: asyncio.Task | None = None
    latest_frame: bytes | None = None
    latest_counts: dict = field(default_factory=dict)
    alert_sent_until: float = 0.0


class CameraManager:
    def __init__(self, detectors: dict[str, PPEDetector]) -> None:
        self.detectors = detectors

        self._entries: dict[int, _CameraEntry] = {}
        self._ws_subscribers: dict[int, list[asyncio.Queue]] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._locks: dict[int, asyncio.Lock] = {}

        self._checkers: dict[str, BaseViolationChecker] = {
            "construction": ConstructionViolationChecker(
                cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS,
                persist_seconds=settings.VIOLATION_PERSIST_SECONDS,
            ),
            "medical": MedicalViolationChecker(
                cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS,
                persist_seconds=settings.MEDICAL_VIOLATION_PERSIST_SECONDS,
            ),
        }

        self._dispatcher = AlertDispatcher(self._build_alert_handlers())

    def _build_alert_handlers(self) -> list[AlertHandler]:
        handlers: list[AlertHandler] = []
        if settings.SENDER_EMAIL and settings.RECEIVER_EMAIL and settings.EMAIL_PASSWORD:
            handlers.append(EmailHandler())
        if settings.WEBHOOK_URL:
            handlers.append(WebhookHandler(settings.WEBHOOK_URL, timeout=settings.WEBHOOK_TIMEOUT_SECONDS))
        return handlers

    def _get_lock(self, camera_id: int) -> asyncio.Lock:
        if camera_id not in self._locks:
            self._locks[camera_id] = asyncio.Lock()
        return self._locks[camera_id]

    async def start(self) -> None:
        try:
            from app.db.session import AsyncSessionLocal
            from app.db.models import Camera
            from sqlalchemy import select

            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Camera).where(Camera.is_active == True))  # noqa: E712
                cameras = result.scalars().all()
        except Exception as exc:
            logger.warning("Could not load active cameras from DB: %s", exc)
            cameras = []

        for cam in cameras:
            try:
                await self._launch_camera(cam.id, cam.profile, cam.source_type, cam.source_uri, cam.enabled_classes)
            except Exception as exc:
                logger.warning("Failed to restore camera %d on startup: %s", cam.id, exc)

        self._cleanup_task = asyncio.create_task(self._cleanup_loop(), name="frame-cleanup")

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        for entry in list(self._entries.values()):
            if entry.task:
                entry.task.cancel()
                try:
                    await entry.task
                except asyncio.CancelledError:
                    pass
            await entry.source.release()
        self._entries.clear()

    # ------------------------------------------------------------------
    # Source building
    # ------------------------------------------------------------------

    def _validate_rtsp_uri(self, uri: str) -> None:
        allowed = [p.strip() for p in settings.ALLOWED_RTSP_PREFIXES.split(",") if p.strip()]
        if not allowed:
            return
        if not any(uri.startswith(p) for p in allowed):
            raise ValueError(f"RTSP source not allowed by ALLOWED_RTSP_PREFIXES: {allowed}")

    def _build_source(self, source_type: str, source_uri: str) -> CameraSource:
        if source_type == "webcam":
            from app.camera.webcam_source import WebcamSource

            try:
                idx = int(source_uri)
            except (TypeError, ValueError):
                raise ValueError("webcam source_uri must be an integer index like '0' or '1'")
            return WebcamSource(idx)

        if source_type == "rtsp":
            from app.camera.rtsp_source import RTSPSource

            self._validate_rtsp_uri(source_uri)
            return RTSPSource(source_uri)

        if source_type == "file":
            from app.camera.file_source import FileSource

            return FileSource(source_uri)

        raise ValueError(f"Unknown source_type: {source_type!r}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _launch_camera(
        self,
        camera_id: int,
        profile: Profile,
        source_type: str,
        source_uri: str,
        enabled_classes: list[str] | None = None,
    ) -> bool:
        async with self._get_lock(camera_id):
            if (
                camera_id in self._entries
                and self._entries[camera_id].task
                and not self._entries[camera_id].task.done()
            ):
                logger.warning("Camera %d already running", camera_id)
                return False

            source = self._build_source(source_type, source_uri)
            connected = await source.connect()
            if not connected:
                return False

            entry = _CameraEntry(
                camera_id=camera_id,
                profile=profile,
                source=source,
                enabled_classes=sanitize_enabled_classes(profile, enabled_classes),
            )
            self._entries[camera_id] = entry
            entry.task = asyncio.create_task(self._process_loop(entry), name=f"camera-{camera_id}")
            logger.info("Camera %d processing started (profile=%s)", camera_id, profile)
            return True

    async def start_camera(
        self,
        camera_id: int,
        profile: Profile,
        source_type: str,
        source_uri: str,
        enabled_classes: list[str] | None = None,
    ) -> bool:
        return await self._launch_camera(camera_id, profile, source_type, source_uri, enabled_classes)

    async def stop_camera(self, camera_id: int) -> bool:
        async with self._get_lock(camera_id):
            entry = self._entries.get(camera_id)
            if entry is None:
                return False

            if entry.task:
                entry.task.cancel()
                try:
                    await entry.task
                except asyncio.CancelledError:
                    pass

            await entry.source.release()
            self._entries.pop(camera_id, None)

            # reset checker state
            self._checkers[entry.profile].reset(camera_id)

            logger.info("Camera %d stopped", camera_id)
            return True

    def update_enabled_classes(self, camera_id: int, enabled_classes: list[str] | None) -> None:
        entry = self._entries.get(camera_id)
        if not entry:
            return
        entry.enabled_classes = sanitize_enabled_classes(entry.profile, enabled_classes)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    @staticmethod
    def _count_by_name(detections: list, name: str) -> int:
        key = (name or "").strip().lower()
        return sum(1 for d in detections if (d.class_name or "").strip().lower() == key)

    def _compute_counts(self, profile: Profile, detections: list) -> dict:
        if profile == "construction":
            return {
                "hardhat": self._count_by_name(detections, "Hardhat"),
                "vest": self._count_by_name(detections, "Safety Vest"),
                "person": self._count_by_name(detections, "Person"),
                "no_mask": self._count_by_name(detections, "NO-Mask"),
                "no_gloves": self._count_by_name(detections, "NO-Gloves"),
                "total": len(detections),
            }
        else:
            return {
                "no_mask": self._count_by_name(detections, "no mask"),
                "no_gloves": self._count_by_name(detections, "no hand gloves"),
                "no_cap": self._count_by_name(detections, "no head cap"),
                "total": len(detections),
            }

    def _stats_lines(self, profile: Profile, counts: dict) -> list[str]:
        if profile == "construction":
            return [
                f"Hardhats: {counts.get('hardhat',0)}",
                f"Safety Vests: {counts.get('vest',0)}",
                f"People: {counts.get('person',0)}",
            ]
        else:
            return [
                f"NO-Mask: {counts.get('no_mask',0)}",
                f"NO-Gloves: {counts.get('no_gloves',0)}",
                f"NO-HeadCap: {counts.get('no_cap',0)}",
            ]

    async def _save_violation_frame(self, loop: asyncio.AbstractEventLoop, camera_id: int, frame) -> str:
        frame_dir = os.path.join(settings.FRAMES_DIR, f"camera_{camera_id}")
        os.makedirs(frame_dir, exist_ok=True)
        fname = f"violation_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
        abs_path = os.path.join(frame_dir, fname)
        await loop.run_in_executor(None, cv2.imwrite, abs_path, frame)
        return f"camera_{camera_id}/{fname}".replace("\\", "/")

    async def _handle_violations(self, entry: _CameraEntry, violations: list, frame) -> None:
        if not violations:
            return

        loop = asyncio.get_running_loop()
        rel_path = await self._save_violation_frame(loop, entry.camera_id, frame)
        entry.alert_sent_until = time.time() + settings.ALERT_DISPLAY_SECONDS

        for violation in violations:
            violation.frame_path = rel_path

            violation_id = await save_violation(violation)
            violation.violation_id = violation_id
            await record_alert_log(
                violation_id=violation_id,
                handler_type="db",
                success=violation_id is not None,
                error_msg=None if violation_id is not None else "Failed to persist violation row",
            )

            await self._dispatcher.dispatch(violation)

    async def _process_loop(self, entry: _CameraEntry) -> None:
        camera_id = entry.camera_id
        loop = asyncio.get_running_loop()

        detector = self.detectors[entry.profile]
        checker = self._checkers[entry.profile]

        try:
            while True:
                frame = await entry.source.read_frame()
                if frame is None:
                    await asyncio.sleep(settings.FRAME_READ_RETRY_DELAY_SECONDS)
                    continue

                detections = await loop.run_in_executor(None, detector.detect, frame)
                entry.latest_counts = self._compute_counts(entry.profile, detections)
                # debug: مرة كل 5 ثواني لو فيه كشف أو صفر مستمر
                now_ts = time.time()
                if now_ts - getattr(entry, "_last_det_log", 0) >= 5:
                    entry._last_det_log = now_ts  # type: ignore[attr-defined]
                    sample = [(d.class_name, round(d.confidence, 2)) for d in detections[:8]]
                    logger.info("cam=%d profile=%s dets=%s", camera_id, entry.profile, sample)
                violations = checker.check(camera_id, detections, enabled_classes=entry.enabled_classes)
                await self._handle_violations(entry, violations, frame)

                show_alert = time.time() < entry.alert_sent_until
                annotated = annotate_frame(
                    frame,
                    detections,
                    stats_lines=self._stats_lines(entry.profile, entry.latest_counts),
                    show_alert_sent=show_alert,
                )
                resized = cv2.resize(annotated, (640, 480))
                _, jpeg = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
                entry.latest_frame = jpeg.tobytes()

                await self._broadcast(camera_id, entry.latest_counts)
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.exception("Error in camera %d processing loop: %s", camera_id, exc)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await self._cleanup_old_frames()
            except Exception as exc:
                logger.warning("Frame cleanup cycle failed: %s", exc)
            await asyncio.sleep(settings.FRAME_CLEANUP_INTERVAL_HOURS * 3600)

    async def _cleanup_old_frames(self) -> None:
        if settings.MAX_FRAME_AGE_DAYS <= 0:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._delete_old_frames_sync)

    @staticmethod
    def _delete_old_frames_sync() -> None:
        cutoff = time.time() - (settings.MAX_FRAME_AGE_DAYS * 86400)
        removed = 0
        for root, _dirs, files in os.walk(settings.FRAMES_DIR):
            for fname in files:
                if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
                        removed += 1
                except OSError:
                    continue
        if removed:
            logger.info("Frame cleanup: removed %d old violation frame(s)", removed)

    # ------------------------------------------------------------------
    # WebSocket broadcasting
    # ------------------------------------------------------------------

    async def _broadcast(self, camera_id: int, data: dict) -> None:
        queues = self._ws_subscribers.get(camera_id, [])
        for q in list(queues):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    def subscribe(self, camera_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._ws_subscribers.setdefault(camera_id, []).append(q)
        return q

    def unsubscribe(self, camera_id: int, q: asyncio.Queue) -> None:
        subs = self._ws_subscribers.get(camera_id, [])
        if q in subs:
            subs.remove(q)

    def get_latest_frame(self, camera_id: int) -> bytes | None:
        entry = self._entries.get(camera_id)
        return entry.latest_frame if entry else None

    def is_running(self, camera_id: int) -> bool:
        entry = self._entries.get(camera_id)
        return entry is not None and entry.task is not None and not entry.task.done()

    def active_count(self) -> int:
        return sum(1 for cid in self._entries if self.is_running(cid))

    def counts_snapshot(self) -> dict[str, dict]:
        return {
            str(cid): entry.latest_counts
            for cid, entry in self._entries.items()
            if self.is_running(cid)
        }