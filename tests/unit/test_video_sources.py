from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from app.camera.file_source import FileSource
from app.camera.rtsp_source import RTSPSource
from app.core.config import settings


@pytest.mark.parametrize("fps", [0, -10, float("nan"), float("inf"), 999])
async def test_file_source_has_safe_fps_and_eof_does_not_rewind(monkeypatch, fps):
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.get.return_value = fps
    capture.read.side_effect = [(True, np.zeros((8, 8, 3), dtype=np.uint8)), (False, None)]
    monkeypatch.setattr(cv2, "VideoCapture", lambda *_args: capture)
    source = FileSource("synthetic.avi")
    assert await source.connect()
    assert source._fps == 25
    assert await source.read_frame() is not None
    assert await source.read_frame() is None
    assert source.exhausted
    capture.set.assert_not_called()  # no CAP_PROP_POS_FRAMES rewind
    await source.release()
    await source.release()  # idempotent teardown
    capture.release.assert_called_once()
    assert not source.is_open


@pytest.mark.parametrize("source_type", ["file", "rtsp"])
async def test_cancelled_native_read_cannot_race_capture_release(monkeypatch, source_type):
    entered, unblock = threading.Event(), threading.Event()
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.get.return_value = 25

    def blocking_read():
        entered.set()
        assert unblock.wait(timeout=3)
        return True, np.zeros((8, 8, 3), dtype=np.uint8)

    capture.read.side_effect = blocking_read
    monkeypatch.setattr(cv2, "VideoCapture", lambda *_args: capture)
    source = (
        FileSource("synthetic.avi")
        if source_type == "file"
        else RTSPSource("rtsp://192.168.10.20/live")
    )
    assert await source.connect()
    reader = asyncio.create_task(source.read_frame())
    assert await asyncio.to_thread(entered.wait, 1)
    reader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reader
    releaser = asyncio.create_task(source.release())
    try:
        await asyncio.sleep(0.03)
        capture.release.assert_not_called()
    finally:
        unblock.set()
    await asyncio.wait_for(releaser, timeout=2)
    capture.release.assert_called_once()
    assert not source.is_open


async def test_rtsp_configures_finite_ffmpeg_open_and_read_timeouts(monkeypatch):
    capture = MagicMock()
    capture.isOpened.return_value = True
    factory = MagicMock(return_value=capture)
    monkeypatch.setattr(cv2, "VideoCapture", factory)
    monkeypatch.setattr(settings, "RTSP_OPEN_TIMEOUT_SECONDS", 0.125)
    monkeypatch.setattr(settings, "RTSP_READ_TIMEOUT_SECONDS", 0.750)
    source = RTSPSource("rtsp://192.168.10.20/live")
    assert await source.connect()
    factory.assert_called_once_with(
        source.url,
        cv2.CAP_FFMPEG,
        [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 125, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 750],
    )
    await source.release()


@pytest.mark.parametrize("source_type", ["file", "rtsp"])
async def test_failed_capture_connect_releases_handle_and_stays_closed(monkeypatch, source_type):
    capture = MagicMock()
    capture.isOpened.return_value = False
    monkeypatch.setattr(cv2, "VideoCapture", lambda *_args: capture)
    source = (
        FileSource("synthetic.avi")
        if source_type == "file"
        else RTSPSource("rtsp://192.168.10.20/live")
    )
    assert not await source.connect()
    assert not source.is_open
    assert await source.read_frame() is None
    await source.release()
    capture.release.assert_called_once()
