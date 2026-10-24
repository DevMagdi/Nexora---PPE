from __future__ import annotations

from unittest.mock import MagicMock

import cv2

from app.camera.capture_utils import configure_capture_buffer
from app.camera.rtsp_source import RTSPSource
from app.core.config import settings


def test_capture_buffer_asks_opencv_for_configured_depth():
    capture = MagicMock()
    capture.set.return_value = True

    assert configure_capture_buffer(capture, source_name="RTSP", buffer_size=1) is True
    capture.set.assert_called_once_with(cv2.CAP_PROP_BUFFERSIZE, 1)


def test_unsupported_capture_buffer_is_a_non_fatal_hint():
    capture = MagicMock()
    capture.set.return_value = False

    assert configure_capture_buffer(capture, source_name="RTSP", buffer_size=1) is False
    capture.set.assert_called_once_with(cv2.CAP_PROP_BUFFERSIZE, 1)


def test_capture_backend_exception_does_not_prevent_camera_startup():
    capture = MagicMock()
    capture.set.side_effect = RuntimeError("backend does not support buffer property")

    assert configure_capture_buffer(capture, source_name="RTSP", buffer_size=1) is False


def test_invalid_buffer_depth_does_not_call_backend():
    capture = MagicMock()

    assert configure_capture_buffer(capture, source_name="RTSP", buffer_size=0) is False
    capture.set.assert_not_called()


async def test_live_sources_apply_the_configured_buffer_size(monkeypatch):
    source = RTSPSource("rtsp://192.168.10.20/live")
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.set.return_value = True
    monkeypatch.setattr(cv2, "VideoCapture", lambda *_args: capture)
    monkeypatch.setattr(settings, "CAMERA_CAPTURE_BUFFER_SIZE", 2)

    assert await source.connect() is True
    capture.set.assert_called_once_with(cv2.CAP_PROP_BUFFERSIZE, 2)
    await source.release()
