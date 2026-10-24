from __future__ import annotations

import asyncio
import contextlib
import os
import time
import uuid
from dataclasses import dataclass, field

import cv2

from app.alerts.base import AlertHandler
from app.alerts.dispatcher import AlertDispatcher
from app.alerts.email_handler import EmailHandler
from app.alerts.webhook_handler import SlackWebhookHandler, WebhookHandler
from app.camera.source import CameraSource
from app.camera.source_security import validate_file_uri, validate_rtsp_uri
from app.core.config import settings
from app.core.detector import PPEDetector
from app.core.frame_annotator import annotate_frame
from app.core.logging import get_logger
from app.core.ppe import canonical_class_name, display_classes, sanitize_enabled_classes
from app.core.violation_checker import ViolationChecker, apply_persist_floor
from app.db.repository import record_alert_log, save_violation

logger = get_logger(__name__)


@dataclass
class _CameraEntry:
    camera_id: int
    source: CameraSource
    enabled_classes: list[str] = field(default_factory=list)
    task: asyncio.Task | None = None
    latest_frame: bytes | None = None
    frame_seq: int = 0
    last_frame_at: float = 0.0
    first_frame_ready: asyncio.Event = field(default_factory=asyncio.Event)
    consecutive_read_failures: int = 0
    last_read_warning_at: float = 0.0
    latest_counts: dict = field(default_factory=dict)
    alert_sent_until: float = 0.0
    last_det_log: float = 0.0
    last_inference_ms: float = 0.0
    last_processing_ms: float = 0.0


class CameraManager:
    def __init__(self, detector: PPEDetector) -> None:
        self.detector = detector

        self._entries: dict[int, _CameraEntry] = {}
        self._ws_subscribers: dict[int, list[asyncio.Queue]] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._locks: dict[int, asyncio.Lock] = {}

        self._checker = ViolationChecker(
            cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS,
            persist_seconds=apply_persist_floor(
                settings.VIOLATION_PERSIST_SECONDS,
                settings.VIOLATION_PERSIST_FLOOR_SECONDS,
            ),
        )

        self._dispatcher = AlertDispatcher(self._build_alert_handlers())

    def _build_alert_handlers(self) -> list[AlertHandler]:
        handlers: list[AlertHandler] = []
        if settings.SENDER_EMAIL and settings.RECEIVER_EMAIL and settings.EMAIL_PASSWORD:
            handlers.append(EmailHandler())
        if settings.SLACK_WEBHOOK_URL:
            handlers.append(
                SlackWebhookHandler(
                    settings.SLACK_WEBHOOK_URL,
                    timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
                )
            )
        if settings.WEBHOOK_URL:
            handlers.append(
                WebhookHandler(
                    settings.WEBHOOK_URL,
                    timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
                )
            )
        return handlers

    def _get_lock(self, camera_id: int) -> asyncio.Lock:
        if camera_id not in self._locks:
            self._locks[camera_id] = asyncio.Lock()
        return self._locks[camera_id]

    async def start(self) -> None:
        try:
            from sqlalchemy import select

            from app.db.models import Camera
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Camera).where(Camera.is_active == True)  # noqa: E712
                )
                cameras = result.scalars().all()
        except Exception as exc:
            logger.warning("Could not load active cameras from DB: %s", exc)
            cameras = []

        for cam in cameras:
            try:
                await self._launch_camera(
                    cam.id,
                    cam.source_type,
                    cam.source_uri,
                    cam.enabled_classes,
                )
            except Exception as exc:
                logger.warning("Failed to restore camera %d on startup: %s", cam.id, exc)

        self._cleanup_task = asyncio.create_task(self._cleanup_loop(), name="frame-cleanup")

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

        for entry in list(self._entries.values()):
            if entry.task:
                entry.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await entry.task
            await entry.source.release()
        self._entries.clear()

    # ------------------------------------------------------------------
    # Source building & validation
    # ------------------------------------------------------------------

    def _build_source(self, source_type: str, source_uri: str) -> CameraSource:
        if source_type == "rtsp":
            from app.camera.rtsp_source import RTSPSource

            validate_rtsp_uri(source_uri)
            return RTSPSource(source_uri)

        if source_type == "file":
            from app.camera.file_source import FileSource

            validated_path = validate_file_uri(source_uri)
            return FileSource(validated_path)

        raise ValueError(f"Unknown source_type: {source_type!r}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _launch_camera(
        self,
        camera_id: int,
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
            logger.info(
                "Opening industrial camera source (camera_id=%d source_type=%s)",
                camera_id,
                source_type,
            )
            try:
                connected = await source.connect()
            except asyncio.CancelledError:
                # An aborted start request can leave a native open running. The
                # source lock makes this wait for that open before releasing it.
                with contextlib.suppress(Exception):
                    await source.release()
                raise
            except Exception as exc:
                logger.error(
                    "Camera source failed to open (camera_id=%d error_type=%s)",
                    camera_id,
                    type(exc).__name__,
                )
                with contextlib.suppress(Exception):
                    await source.release()
                raise ValueError(
                    "Could not open the camera source. Check its URI, permissions, and availability."
                ) from None
            if not connected:
                logger.error(
                    "Camera source did not open (camera_id=%d source_type=%s)",
                    camera_id,
                    source_type,
                )
                with contextlib.suppress(Exception):
                    await source.release()
                return False

            entry = _CameraEntry(
                camera_id=camera_id,
                source=source,
                enabled_classes=sanitize_enabled_classes(enabled_classes),
            )
            self._entries[camera_id] = entry
            entry.task = asyncio.create_task(self._process_loop(entry), name=f"camera-{camera_id}")
            logger.info(
                "Camera %d processing started (enabled_classes=%s)",
                camera_id,
                entry.enabled_classes,
            )
            return True

    async def _wait_for_first_frame(self, entry: _CameraEntry) -> bool:
        if entry.first_frame_ready.is_set():
            return self.is_running(entry.camera_id)
        if entry.task is None or entry.task.done():
            return False

        frame_waiter = asyncio.create_task(entry.first_frame_ready.wait())
        try:
            await asyncio.wait(
                {frame_waiter, entry.task},
                timeout=settings.CAMERA_FIRST_FRAME_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            if not frame_waiter.done():
                frame_waiter.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await frame_waiter
        return entry.first_frame_ready.is_set() and self.is_running(entry.camera_id)

    async def start_camera(
        self,
        camera_id: int,
        source_type: str,
        source_uri: str,
        enabled_classes: list[str] | None = None,
    ) -> bool:
        existing = self._entries.get(camera_id)
        if existing and existing.task and not existing.task.done():
            if self.is_running(camera_id):
                logger.info("Camera %d is already streaming", camera_id)
                return True
            if await self._wait_for_first_frame(existing):
                return True
            logger.warning("Restarting camera %d because no fresh frame is available", camera_id)
            await self.stop_camera(camera_id)

        if not await self._launch_camera(camera_id, source_type, source_uri, enabled_classes):
            return False

        entry = self._entries.get(camera_id)
        if entry is None or not await self._wait_for_first_frame(entry):
            logger.error(
                "Camera %d opened but produced no usable frame within %.1f seconds",
                camera_id,
                settings.CAMERA_FIRST_FRAME_TIMEOUT_SECONDS,
            )
            await self.stop_camera(camera_id)
            raise ValueError(
                "The camera opened but no video frame arrived in time. Check the RTSP address, "
                "network access, camera credentials and video availability."
            )

        logger.info("Camera %d is live and its first processed frame is ready", camera_id)
        return True

    async def stop_camera(self, camera_id: int) -> bool:
        async with self._get_lock(camera_id):
            entry = self._entries.get(camera_id)
            if entry is None:
                return False

            if entry.task:
                entry.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await entry.task

            await entry.source.release()
            self._entries.pop(camera_id, None)

            # reset checker state
            self._checker.reset(camera_id)

            logger.info("Camera %d stopped", camera_id)
            return True

    def update_enabled_classes(self, camera_id: int, enabled_classes: list[str] | None) -> None:
        entry = self._entries.get(camera_id)
        if not entry:
            return
        entry.enabled_classes = sanitize_enabled_classes(enabled_classes)
        self._checker.reset(camera_id)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_detections_for_display(enabled_classes: list[str], detections: list) -> list:
        allowed = display_classes(enabled_classes)
        return [d for d in detections if canonical_class_name(d.class_name) in allowed]

    @staticmethod
    def _compute_counts(detections: list) -> dict:
        keys = {
            "Person": "person",
            "Hardhat": "hardhat",
            "NO-Hardhat": "no_hardhat",
            "Safety Vest": "vest",
            "NO-Safety Vest": "no_vest",
            "Gloves": "gloves",
            "NO-Gloves": "no_gloves",
            "Safety Boots": "boots",
            "NO-Boot": "no_boot",
            "Goggles": "goggles",
            "NO-Goggles": "no_goggles",
        }
        counts = dict.fromkeys(keys.values(), 0)
        for detection in detections:
            key = keys.get(canonical_class_name(detection.class_name))
            if key:
                counts[key] += 1
        counts["total"] = sum(counts.values())
        return counts

    @staticmethod
    def _stats_lines(counts: dict) -> list[str]:
        return [
            f"People: {counts.get('person', 0)}",
            f"Hardhats: {counts.get('hardhat', 0)} | NO-Hardhat: {counts.get('no_hardhat', 0)}",
            f"Safety Vests: {counts.get('vest', 0)} | NO-Vest: {counts.get('no_vest', 0)}",
            f"NO-Gloves: {counts.get('no_gloves', 0)} | NO-Boot: {counts.get('no_boot', 0)}",
            f"NO-Goggles: {counts.get('no_goggles', 0)}",
        ]

    async def _save_violation_frame(
        self, loop: asyncio.AbstractEventLoop, camera_id: int, frame
    ) -> str:
        frame_dir = os.path.join(settings.FRAMES_DIR, f"camera_{camera_id}")
        os.makedirs(frame_dir, exist_ok=True)
        fname = f"violation_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
        abs_path = os.path.join(frame_dir, fname)
        written = await loop.run_in_executor(None, cv2.imwrite, abs_path, frame)
        if not written:
            raise RuntimeError("Could not write the industrial violation evidence frame")
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

        detector = self.detector
        checker = self._checker

        cancelled = False
        try:
            while True:
                cycle_started = time.perf_counter()
                frame = await entry.source.read_frame()
                if frame is None:
                    if getattr(entry.source, "exhausted", False):
                        logger.info("Camera %d video processing completed", camera_id)
                        break
                    checker.reset(camera_id)
                    entry.consecutive_read_failures += 1
                    now = time.monotonic()
                    if (
                        entry.consecutive_read_failures == 1
                        or now - entry.last_read_warning_at >= 5.0
                    ):
                        logger.warning(
                            "Camera %d source is open but returned no frame (%d consecutive read failures)",
                            camera_id,
                            entry.consecutive_read_failures,
                        )
                        entry.last_read_warning_at = now
                    await asyncio.sleep(settings.FRAME_READ_RETRY_DELAY_SECONDS)
                    continue

                if entry.consecutive_read_failures:
                    logger.info(
                        "Camera %d recovered frame input after %d failed read(s)",
                        camera_id,
                        entry.consecutive_read_failures,
                    )
                    entry.consecutive_read_failures = 0

                inference_started = time.perf_counter()
                detections = await loop.run_in_executor(None, detector.detect, frame)
                entry.last_inference_ms = (time.perf_counter() - inference_started) * 1000
                display_detections = self._filter_detections_for_display(
                    entry.enabled_classes, detections
                )
                entry.latest_counts = self._compute_counts(display_detections)

                violations = checker.check(
                    camera_id, detections, enabled_classes=entry.enabled_classes
                )
                if violations:
                    evidence = annotate_frame(frame, display_detections, [])
                    await self._handle_violations(entry, violations, evidence)

                show_alert = time.time() < entry.alert_sent_until
                display_counts = self._compute_counts(display_detections)
                annotated = annotate_frame(
                    frame,
                    display_detections,
                    stats_lines=self._stats_lines(display_counts),
                    show_alert_sent=show_alert,
                )
                resized = cv2.resize(annotated, (640, 480))
                _, jpeg = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
                entry.latest_frame = jpeg.tobytes()
                entry.frame_seq += 1
                entry.last_frame_at = time.monotonic()
                if not entry.first_frame_ready.is_set():
                    entry.first_frame_ready.set()
                    height, width = frame.shape[:2]
                    logger.info(
                        "Camera %d first processed frame ready (%dx%d)",
                        camera_id,
                        width,
                        height,
                    )

                await self._broadcast(camera_id, entry.latest_counts)
                entry.last_processing_ms = (time.perf_counter() - cycle_started) * 1000

                now_ts = time.time()
                if now_ts - entry.last_det_log >= 5:
                    entry.last_det_log = now_ts
                    sample = [
                        (
                            d.class_name,
                            round(d.confidence, 2),
                            d.source,
                            (d.x1, d.y1, d.x2, d.y2),
                        )
                        for d in detections[:12]
                    ]
                    logger.info(
                        "cam=%d dets=%s inference_ms=%.1f cycle_ms=%.1f",
                        camera_id,
                        sample,
                        entry.last_inference_ms,
                        entry.last_processing_ms,
                    )

                await asyncio.sleep(0)

        except asyncio.CancelledError:
            cancelled = True
        except Exception as exc:
            logger.error("Camera %d processing failed (%s)", camera_id, type(exc).__name__)
        finally:
            checker.reset(camera_id)
            await entry.source.release()
            if not cancelled:
                await self._mark_inactive(camera_id)

    @staticmethod
    async def _mark_inactive(camera_id: int) -> None:
        from app.db.models import Camera
        from app.db.session import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                camera = await session.get(Camera, camera_id)
                if camera:
                    camera.is_active = False
                    await session.commit()
        except Exception:
            logger.warning("Could not mark completed camera %d inactive", camera_id)

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
    # WebSocket & Stream helpers
    # ------------------------------------------------------------------

    async def _broadcast(self, camera_id: int, data: dict) -> None:
        queues = self._ws_subscribers.get(camera_id, [])
        for q in list(queues):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(data)

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

    def get_latest_frame_with_seq(self, camera_id: int) -> tuple[bytes | None, int]:
        entry = self._entries.get(camera_id)
        if entry is None:
            return None, 0
        return entry.latest_frame, entry.frame_seq

    def get_latest_counts(self, camera_id: int) -> dict | None:
        entry = self._entries.get(camera_id)
        return entry.latest_counts if entry and entry.latest_counts else None

    def is_running(self, camera_id: int) -> bool:
        entry = self._entries.get(camera_id)
        if entry is None or entry.task is None or entry.task.done() or entry.frame_seq == 0:
            return False
        return time.monotonic() - entry.last_frame_at < settings.CAMERA_FRAME_STALE_SECONDS

    def active_count(self) -> int:
        return sum(1 for cid in self._entries if self.is_running(cid))

    def counts_snapshot(self) -> dict[str, dict]:
        return {
            str(cid): entry.latest_counts
            for cid, entry in self._entries.items()
            if self.is_running(cid)
        }
