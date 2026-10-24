"""Real OpenCV video/storage/SQL integration with an explicitly synthetic detector.

These tests validate the processing pipeline, NOT approved-model accuracy.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.camera.manager import CameraManager
from app.core.config import settings
from app.core.detector import DANGER_BGR, Detection
from app.db.models import AlertLog, Camera, Violation


def make_video(path: Path, *, frames: int = 12, fps: float = 20) -> bytes:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (128, 96))
    assert writer.isOpened(), "OpenCV MJPG support is required for this integration test"
    for index in range(frames):
        frame = np.zeros((96, 128, 3), dtype=np.uint8)
        frame[60:80, :, :] = index * 10
        writer.write(frame)
    writer.release()
    return path.read_bytes()


class SyntheticDetector:
    """Known test detections; deliberately not an ML inference implementation."""

    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return [
            Detection(0, "Person", 0.95, 10, 10, 100, 90),
            Detection(2, "NO-Hardhat", 0.90, 20, 20, 50, 45, DANGER_BGR),
            Detection(10, "NO-Goggles", 0.90, 30, 30, 55, 50, DANGER_BGR),
        ]


async def test_uploaded_video_runs_once_through_evidence_alert_database_and_api(
    test_client, db_session, monkeypatch, tmp_path
):
    import app.db.session as database

    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    monkeypatch.setattr(database, "AsyncSessionLocal", factory)
    monkeypatch.setattr(settings, "ALLOWED_VIDEO_DIR", str(tmp_path / "videos"))
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "videos" / "uploads"))
    monkeypatch.setattr(settings, "FRAMES_DIR", str(tmp_path / "evidence"))
    # Exercise persistence/cooldown without spending eight seconds per unit run.
    monkeypatch.setattr(settings, "VIOLATION_PERSIST_SECONDS", 0)
    monkeypatch.setattr(settings, "VIOLATION_PERSIST_FLOOR_SECONDS", 0)
    detector = SyntheticDetector()
    manager = CameraManager(detector)
    manager._dispatcher.handlers = []
    app = test_client._transport.app
    app.state.camera_manager = manager
    app.state.detector = detector
    source_bytes = make_video(tmp_path / "synthetic.avi")
    response = await test_client.post(
        "/api/v1/inference/video",
        files={"file": ("loading-bay.avi", source_bytes, "video/x-msvideo")},
        data={"name": "Synthetic loading bay", "enabled_classes": "helmet"},
    )
    assert response.status_code == 201, response.text
    camera_id = response.json()["id"]
    queue = manager.subscribe(camera_id)
    try:
        started_at = time.monotonic()
        response = await test_client.post(f"/api/v1/cameras/{camera_id}/start")
        assert response.status_code == 200, response.text
        entry = manager._entries[camera_id]
        assert entry.first_frame_ready.is_set()
        assert manager.is_running(camera_id)
        counts = await asyncio.wait_for(queue.get(), timeout=1)
        assert counts["person"] == 1
        assert counts["no_hardhat"] == 1
        assert counts["no_goggles"] == 0  # disabled rules never leak into live counts
        await asyncio.wait_for(entry.task, timeout=5)
        assert time.monotonic() - started_at >= 0.45  # recorded FPS, not a tight replay loop
        assert detector.calls == 12
        assert entry.frame_seq == 12
        assert entry.source.exhausted
        assert not entry.source.is_open
        assert not manager.is_running(camera_id)
        assert manager.active_count() == 0
        assert manager.counts_snapshot() == {}
        assert not manager._checker._states
        assert entry.latest_frame and entry.latest_frame.startswith(b"\xff\xd8")

        db_session.expire_all()
        camera = await db_session.get(Camera, camera_id)
        assert not camera.is_active  # EOF must not auto-replay after an application restart
        events = (await db_session.execute(select(Violation))).scalars().all()
        assert len(events) == 1
        event = events[0]
        assert event.violation_type == "NO-Hardhat"
        assert event.confidence == 0.90
        evidence = Path(settings.FRAMES_DIR) / event.frame_path
        image = cv2.imread(str(evidence))
        assert image is not None and image.shape == (96, 128, 3)
        assert np.count_nonzero(image[15:50, 15:55]) > 200  # annotated bounding box/text
        alert = (await db_session.execute(select(AlertLog))).scalar_one()
        assert alert.handler_type == "db" and alert.success
        assert alert.violation_id == event.id

        log = await test_client.get("/api/v1/violations", params={"camera_id": camera_id})
        assert log.status_code == 200 and log.json()["total"] == 1
        media = await test_client.get(log.json()["items"][0]["frame_url"])
        assert media.status_code == 200 and media.headers["content-type"] == "image/jpeg"
        summary = await test_client.get("/api/v1/dashboard", params={"range": "24h"})
        assert summary.json()["total_events"] == 1
        assert summary.json()["open_events"] == 1
        response = await test_client.post(f"/api/v1/violations/{event.id}/resolve")
        assert response.status_code == 200 and response.json()["is_resolved"]
    finally:
        manager.unsubscribe(camera_id, queue)
        await manager.stop()


async def test_shutdown_releases_sources_but_keeps_explicitly_active_restart_intent(
    db_session, monkeypatch
):
    import app.db.session as database

    monkeypatch.setattr(
        database, "AsyncSessionLocal", async_sessionmaker(db_session.bind, expire_on_commit=False)
    )
    camera = Camera(
        name="Restart intent",
        source_type="rtsp",
        source_uri="rtsp://192.168.10.20/live",
        is_active=True,
    )
    db_session.add(camera)
    await db_session.commit()

    class RepeatingSource:
        released = False

        async def connect(self):
            return True

        async def read_frame(self):
            await asyncio.sleep(0.02)
            return np.zeros((96, 128, 3), dtype=np.uint8)

        async def release(self):
            self.released = True

    class EmptyDetector:
        def detect(self, frame):
            return []

    source = RepeatingSource()
    manager = CameraManager(EmptyDetector())
    monkeypatch.setattr(manager, "_build_source", lambda *_args: source)
    assert await manager.start_camera(camera.id, "rtsp", camera.source_uri)
    await manager.stop()
    await db_session.refresh(camera)
    assert source.released and camera.is_active
    assert not manager._entries


async def test_inference_failure_releases_source_and_marks_camera_inactive(
    db_session, monkeypatch, tmp_path
):
    import app.db.session as database

    monkeypatch.setattr(
        database, "AsyncSessionLocal", async_sessionmaker(db_session.bind, expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "ALLOWED_VIDEO_DIR", str(tmp_path))
    path = tmp_path / "synthetic.avi"
    make_video(path)
    camera = Camera(
        name="Failure cleanup", source_type="file", source_uri=str(path), is_active=True
    )
    db_session.add(camera)
    await db_session.commit()

    class FailingDetector:
        def detect(self, frame):
            raise RuntimeError("Explicit test-only inference failure")

    manager = CameraManager(FailingDetector())
    assert await manager._launch_camera(camera.id, "file", str(path))
    entry = manager._entries[camera.id]
    await asyncio.wait_for(entry.task, timeout=3)
    await db_session.refresh(camera)
    assert not camera.is_active
    assert not entry.source.is_open
    assert not manager.is_running(camera.id)
    assert not manager._checker._states
    await manager.stop()
