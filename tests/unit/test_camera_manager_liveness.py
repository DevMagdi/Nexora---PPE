from __future__ import annotations

import asyncio

import numpy as np
import pytest

from app.camera.manager import CameraManager
from app.core.config import settings


class FakeSource:
    def __init__(self, *, frame: np.ndarray | None):
        self.frame = frame
        self.released = False

    async def connect(self) -> bool:
        return True

    async def read_frame(self) -> np.ndarray | None:
        await asyncio.sleep(0)
        return self.frame

    async def release(self) -> None:
        self.released = True

    @property
    def is_open(self) -> bool:
        return not self.released


class FakeDetector:
    def detect(self, frame: np.ndarray) -> list:
        return []


def manager_with_source(monkeypatch, source: FakeSource) -> CameraManager:
    manager = CameraManager({"construction": FakeDetector()})
    monkeypatch.setattr(manager, "_build_source", lambda *_args: source)
    return manager


async def test_start_camera_waits_until_first_processed_frame(monkeypatch):
    source = FakeSource(frame=np.zeros((32, 48, 3), dtype=np.uint8))
    manager = manager_with_source(monkeypatch, source)

    started = await manager.start_camera(1, "construction", "webcam", "0")

    assert started is True
    assert manager.is_running(1) is True
    entry = manager._entries[1]
    assert entry.first_frame_ready.is_set()
    assert entry.latest_frame is not None
    assert entry.frame_seq >= 1

    await manager.stop_camera(1)
    assert source.released is True
    assert manager.is_running(1) is False


async def test_start_camera_fails_clearly_and_releases_source_without_frames(monkeypatch):
    source = FakeSource(frame=None)
    manager = manager_with_source(monkeypatch, source)
    monkeypatch.setattr(settings, "CAMERA_FIRST_FRAME_TIMEOUT_SECONDS", 0.04)
    monkeypatch.setattr(settings, "FRAME_READ_RETRY_DELAY_SECONDS", 0.001)

    with pytest.raises(ValueError, match="no video frame arrived"):
        await manager.start_camera(2, "construction", "webcam", "0")

    assert source.released is True
    assert 2 not in manager._entries
    assert manager.is_running(2) is False
