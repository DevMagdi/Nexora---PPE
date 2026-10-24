"""Development-only local USB capture isolated from a blocking native driver."""

from __future__ import annotations

import asyncio
import multiprocessing
from multiprocessing.connection import Connection

import cv2
import numpy as np

from app.camera.http_client import SourceError
from app.camera.source import CameraSource
from app.camera.source_security import validate_usb_index
from app.core.config import settings


def _usb_worker(index: int, connection: Connection) -> None:
    capture = None
    try:
        capture = cv2.VideoCapture(index)
        connection.send(("open", bool(capture.isOpened())))
        if not capture.isOpened():
            return
        while connection.recv() == "read":
            ok, frame = capture.read()
            if ok and frame is not None:
                height, width = frame.shape[:2]
                if width * height > 16_000_000:
                    connection.send(("frame", None))
                    continue
                if width > 960:
                    frame = cv2.resize(frame, (960, max(1, round(height * 960 / width))))
            connection.send(("frame", frame if ok else None))
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        if capture is not None:
            capture.release()
        connection.close()


class USBSource(CameraSource):
    def __init__(self, device_index: int) -> None:
        self.device_index = device_index
        self._process = None
        self._connection: Connection | None = None
        self._opened = False
        self.last_error: str | None = None

    def _receive(self, timeout: float):
        if self._connection is None or not self._connection.poll(timeout):
            raise SourceError("انتهت مهلة جهاز USB المحلي؛ تحقق من الجهاز والصلاحيات.")
        try:
            return self._connection.recv()
        except (EOFError, OSError):
            raise SourceError("توقّف جهاز USB المحلي أو تعذّر فتحه.") from None

    async def connect(self) -> bool:
        await self.release()
        index = validate_usb_index(self.device_index)  # enforce policy again on every reopen
        context = multiprocessing.get_context("spawn")
        self._connection, child = context.Pipe()
        self._process = context.Process(target=_usb_worker, args=(index, child), daemon=True)
        self._process.start()
        child.close()
        _, self._opened = await asyncio.to_thread(self._receive, settings.USB_OPEN_TIMEOUT_SECONDS)
        if not self._opened:
            self.last_error = "تعذّر فتح USB المحلي؛ هذا المصدر للتطوير فقط وليس للإنتاج."
        return self._opened

    async def read_frame(self) -> np.ndarray | None:
        if not self._opened or self._connection is None:
            return None
        self._connection.send("read")
        _, frame = await asyncio.to_thread(self._receive, settings.USB_READ_TIMEOUT_SECONDS)
        return frame

    async def release(self) -> None:
        self._opened = False
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            await asyncio.to_thread(self._process.join, 1.0)
            if self._process.is_alive():
                self._process.kill()
                await asyncio.to_thread(self._process.join, 1.0)
            self._process.close()
            self._process = None

    @property
    def is_open(self) -> bool:
        return self._opened and self._process is not None and self._process.is_alive()
