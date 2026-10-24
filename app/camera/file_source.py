from __future__ import annotations

import asyncio
import math
import threading
import time

import cv2
import numpy as np

from app.camera.source import CameraSource


class FileSource(CameraSource):
    """Process uploaded/site videos once, at their recorded frame rate."""

    reconnect_allowed = False

    def __init__(self, path: str) -> None:
        self.path = path
        self.exhausted = False
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._fps = 25.0
        self._next_frame_at = 0.0

    def _open(self) -> bool:
        with self._lock:
            self._cap = cv2.VideoCapture(self.path)
            if not self._cap.isOpened():
                self._cap.release()
                self._cap = None
                return False
            fps = self._cap.get(cv2.CAP_PROP_FPS)
            self._fps = fps if math.isfinite(fps) and 0 < fps <= 240 else 25.0
            self._next_frame_at = time.monotonic()
            self.exhausted = False
            return True

    async def connect(self) -> bool:
        return await asyncio.to_thread(self._open)

    def _read(self) -> np.ndarray | None:
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            ok, frame = self._cap.read()
            if not ok:
                self.exhausted = True
            return frame if ok else None

    async def read_frame(self) -> np.ndarray | None:
        await asyncio.sleep(max(0.0, self._next_frame_at - time.monotonic()))
        frame = await asyncio.to_thread(self._read)
        self._next_frame_at = max(self._next_frame_at + 1 / self._fps, time.monotonic())
        return frame

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
