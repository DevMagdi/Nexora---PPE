from __future__ import annotations

import asyncio
import io

import cv2
import numpy as np
from PIL import Image

from app.camera.http_client import MediaHTTPClient, SourceError
from app.camera.source import CameraSource
from app.core.config import settings

MAX_JPEG_BYTES = 8 * 1024 * 1024


class MJPEGSource(CameraSource):
    """Decode multipart MJPEG with bounded buffers, verified TLS and read deadlines."""

    def __init__(self, uri: str, auth_mode: str = "basic") -> None:
        self.uri, self.auth_mode = uri, auth_mode
        self._http: MediaHTTPClient | None = None
        self._response = None
        self._chunks = None
        self._buffer = b""
        self.last_error: str | None = None

    async def connect(self) -> bool:
        await self.release()
        self._http = MediaHTTPClient(self.uri, self.auth_mode)
        self._response = await self._http.open(self.uri)
        mime = self._response.headers.get("content-type", "").split(";")[0].strip().lower()
        if mime != "multipart/x-mixed-replace":
            raise SourceError(
                "المسار ليس بث MJPEG متعدد الإطارات؛ لا تستخدم صفحة HTML أو لقطة JPEG ثابتة."
            )
        self._chunks = self._response.aiter_bytes().__aiter__()
        self.last_error = None
        return True

    @staticmethod
    def _decode(jpeg: bytes) -> np.ndarray:
        try:
            with Image.open(io.BytesIO(jpeg)) as image:
                if image.format != "JPEG" or image.width * image.height > settings.MAX_IMAGE_PIXELS:
                    raise ValueError("Invalid dimensions")
                image.verify()
            frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Invalid JPEG")
            return frame
        except (ValueError, OSError, Image.DecompressionBombError):
            raise SourceError("إطار MJPEG تالف أو يتجاوز حد الدقة المسموح.") from None

    async def read_frame(self) -> np.ndarray | None:
        if self._chunks is None:
            return None
        async with asyncio.timeout(settings.HTTP_SOURCE_READ_TIMEOUT_SECONDS):
            while True:
                start = self._buffer.find(b"\xff\xd8")
                end = self._buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                if end >= 0:
                    jpeg, self._buffer = self._buffer[start : end + 2], self._buffer[end + 2 :]
                    return await asyncio.to_thread(self._decode, jpeg)
                if start >= 0:
                    self._buffer = self._buffer[start:]
                elif len(self._buffer) > 65536:
                    raise SourceError("استجابة MJPEG غير صالحة أو بلا إطارات.")
                try:
                    chunk = await anext(self._chunks)
                except StopAsyncIteration:
                    return None
                if len(self._buffer) + len(chunk) > MAX_JPEG_BYTES:
                    raise SourceError("إطار MJPEG يتجاوز حد الحجم المسموح.")
                self._buffer += chunk

    async def release(self) -> None:
        if self._response is not None:
            await self._response.aclose()
        if self._http is not None:
            await self._http.close()
        self._http, self._response, self._chunks = None, None, None
        self._buffer = b""

    @property
    def is_open(self) -> bool:
        return self._response is not None and not self._response.is_closed
