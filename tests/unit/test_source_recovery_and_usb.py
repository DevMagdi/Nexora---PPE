from __future__ import annotations

import asyncio
import multiprocessing
import time
from unittest.mock import AsyncMock

import numpy as np
import pytest

from app.camera.http_client import SourceError
from app.camera.manager import CameraManager
from app.camera.usb_source import USBSource
from app.core.config import settings


class DetectorDouble:
    def detect(self, _frame):
        return []


async def test_retries_are_bounded_and_failure_isolated_to_one_source(monkeypatch):
    class MissingSource:
        connect = AsyncMock(return_value=True)
        read_frame = AsyncMock(side_effect=OSError("NeverLogThisPassword"))
        release = AsyncMock()

    source = MissingSource()
    manager = CameraManager(DetectorDouble())
    monkeypatch.setattr(manager, "_build_source", lambda *_args: source)
    monkeypatch.setattr(manager, "_mark_inactive", AsyncMock())
    monkeypatch.setattr(settings, "CAMERA_MAX_READ_FAILURES", 1)
    monkeypatch.setattr(settings, "CAMERA_RECONNECT_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "CAMERA_RECONNECT_DELAY_SECONDS", 0)
    monkeypatch.setattr(settings, "FRAME_READ_RETRY_DELAY_SECONDS", 0)
    assert await manager._launch_camera(4, "http_mjpeg", "http://camera.test/media/video.mjpg")
    await asyncio.wait_for(manager._entries[4].task, timeout=1)
    assert source.connect.await_count == 3  # initial + two total reopen attempts
    assert manager.get_connection_status(4) == "error"
    assert "NeverLogThisPassword" not in manager.get_last_error(4)
    assert manager.get_latest_frame(4) is None and manager.get_latest_counts(4) is None
    assert not manager.is_running(4)
    await manager.stop()


async def test_a_transient_failure_clears_frames_counts_and_first_frame_gate(monkeypatch):
    fail, recover, cleared, ready_again = (asyncio.Event() for _ in range(4))

    class Source:
        calls = 0

        async def connect(self):
            return True

        async def read_frame(self):
            self.calls += 1
            if self.calls == 2:
                await fail.wait()
                return None
            if self.calls == 3:
                cleared.set()
                await recover.wait()
            if self.calls > 3:
                await asyncio.Event().wait()
            return np.zeros((32, 48, 3), np.uint8)

        async def release(self):
            pass

    source = Source()
    manager = CameraManager(DetectorDouble())
    monkeypatch.setattr(manager, "_build_source", lambda *_args: source)

    async def broadcast(_id, data):
        if "source_status" not in data and source.calls >= 3:
            ready_again.set()

    monkeypatch.setattr(manager, "_broadcast", broadcast)
    try:
        assert await manager.start_camera(1, "rtsp", "rtsp://192.168.10.20/live")
        fail.set()
        await asyncio.wait_for(cleared.wait(), timeout=1)
        assert manager.get_connection_status(1) == "retrying"
        assert manager.get_latest_counts(1) is None
        assert manager.get_latest_frame(1) is None
        assert not manager._entries[1].first_frame_ready.is_set()
        recover.set()
        await asyncio.wait_for(ready_again.wait(), timeout=1)
        assert manager.is_running(1) and manager.get_connection_status(1) == "running"
    finally:
        await manager.stop()


def _blocked_usb_reader(_index, connection):
    # Explicit driver double, not evidence of a working physical USB camera.
    connection.send(("open", True))
    connection.recv()
    time.sleep(60)


async def test_usb_blocked_driver_process_is_terminated_within_deadline(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "dev")
    monkeypatch.setattr(settings, "ENABLE_USB_SOURCES", True)
    monkeypatch.setattr(settings, "USB_READ_TIMEOUT_SECONDS", 0.03)
    monkeypatch.setattr("app.camera.usb_source._usb_worker", _blocked_usb_reader)
    source = USBSource(0)
    try:
        assert await source.connect()
        pid = source._process.pid
        with pytest.raises(SourceError, match="مهلة"):
            await source.read_frame()
        await asyncio.wait_for(source.release(), timeout=2)
        assert source._process is None
        assert pid not in {process.pid for process in multiprocessing.active_children()}
    finally:
        await source.release()


async def test_usb_policy_is_rechecked_before_any_device_or_process_is_opened(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "ENABLE_USB_SOURCES", True)
    source = USBSource(0)
    with pytest.raises(ValueError, match="development-only"):
        await source.connect()
    assert source._process is None
