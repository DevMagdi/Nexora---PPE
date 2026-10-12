from __future__ import annotations

import asyncio

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

    async def connect(self) -> bool:
        loop = asyncio.get_running_loop()
        self._cap = await loop.run_in_executor(None, cv2.VideoCapture, self.url)
        if not self._cap.isOpened():
            # Camera URLs can contain credentials or signed query values; never log them.
            logger.error("Cannot open configured RTSP stream")
            return False
        configure_capture_buffer(
            self._cap,
            source_name="RTSP",
            buffer_size=settings.CAMERA_CAPTURE_BUFFER_SIZE,
        )
        logger.info("Configured RTSP stream opened")
        return True

    async def read_frame(self) -> np.ndarray | None:
        if self._cap is None or not self._cap.isOpened():
            return None
        loop = asyncio.get_running_loop()
        ret, frame = await loop.run_in_executor(None, self._cap.read)
        return frame if ret else None

    async def release(self) -> None:
        if self._cap is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._cap.release)
            self._cap = None

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()