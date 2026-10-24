from __future__ import annotations

import asyncio
import threading

import cv2
import numpy as np

from app.camera.capture_utils import configure_capture_buffer
from app.camera.source import CameraSource
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RTSPSource(CameraSource):
    def __init__(self, url: str) -> None:
        self.url = url
        self._cap: cv2.VideoCapture | None = None
        # A cancelled asyncio future does not stop a native read; serialize release
        # with that read to avoid releasing the capture while OpenCV is using it.
        self._lock = threading.Lock()

    def _open(self) -> bool:
        with self._lock:
            self._cap = cv2.VideoCapture(
                self.url,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    int(settings.RTSP_OPEN_TIMEOUT_SECONDS * 1000),
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    int(settings.RTSP_READ_TIMEOUT_SECONDS * 1000),
                ],
            )
            if not self._cap.isOpened():
                self._cap.release()
                self._cap = None
                logger.error("Cannot open configured RTSP stream")
                return False
            configure_capture_buffer(
                self._cap, source_name="RTSP", buffer_size=settings.CAMERA_CAPTURE_BUFFER_SIZE
            )
            logger.info("Configured RTSP stream opened")
            return True

    async def connect(self) -> bool:
        return await asyncio.to_thread(self._open)

    def _read(self) -> np.ndarray | None:
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            ok, frame = self._cap.read()
            return frame if ok else None

    async def read_frame(self) -> np.ndarray | None:
        return await asyncio.to_thread(self._read)

    def _release(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    async def release(self) -> None:
        await asyncio.to_thread(self._release)

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
