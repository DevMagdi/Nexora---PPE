"""HLS through a guarded fetcher and a network-disabled FFmpeg subprocess.

Supports bounded muxed TS/fMP4 VOD and ordinary live media playlists, including
AES-128 identity keys. No LL-HLS, DRM, separate renditions or arbitrary protocols.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import numpy as np

from app.camera.hls_media import validate_hls_media
from app.camera.http_client import MediaHTTPClient, SourceError
from app.camera.source import CameraSource
from app.camera.source_security import validate_http_uri
from app.core.config import settings

_ATTR = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')
_URI = re.compile(r'URI="([^"]+)"')
_PLAYLIST_LIMIT = 256 * 1024
_SEGMENT_LIMIT = 32 * 1024 * 1024
_UNSUPPORTED = (
    "#EXT-X-PART",
    "#EXT-X-PRELOAD-HINT",
    "#EXT-X-SERVER-CONTROL",
    "#EXT-X-SKIP",
    "#EXT-X-RENDITION-REPORT",
    "#EXT-X-SESSION-KEY",
    "#EXT-X-I-FRAMES-ONLY",
    "#EXT-X-DEFINE",
    "#EXT-X-CONTENT-STEERING",
)


class HLSSource(CameraSource):
    width, height = 960, 540

    def __init__(self, uri: str, auth_mode: str = "basic") -> None:
        self.uri, self.auth_mode = uri, auth_mode
        self._http: MediaHTTPClient | None = None
        self._directory: Path | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._refresh_task: asyncio.Task | None = None
        self._media_uri = uri
        self._interval = 2.0
        self._vod = False
        self.exhausted = False
        self.last_error: str | None = None
        self._generation = 0
        self._first_pts: float | None = None
        self._wall_started = 0.0
        self._last_pts = 0.0
        self._resources: dict[str, tuple[str, int, int]] = {}

    @property
    def is_open(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def reconnect_allowed(self) -> bool:
        return not self._vod  # Do not restart a partly processed VOD as if it were live.

    def _reference(self, base: str, reference: str) -> str:
        if urlsplit(reference).username is not None or "{$" in reference:
            raise SourceError("روابط HLS ببيانات دخول أو متغيرات داخلية غير مدعومة.")
        result = urljoin(base, reference)
        validate_http_uri(result)
        return result

    async def _playlist(self, uri: str) -> list[str]:
        assert self._http is not None
        data = await self._http.fetch(uri, _PLAYLIST_LIMIT)
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise SourceError("قائمة HLS ليست UTF-8 صالحة.") from None
        if not text.startswith("#EXTM3U") or "\x00" in text:
            raise SourceError("العنوان لا يعيد قائمة HLS صالحة.")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) > 1024 or any(line.startswith(_UNSUPPORTED) for line in lines):
            raise SourceError("ميزة HLS هذه غير مدعومة؛ استخدم HLS عاديًا أو وسيط RTSP.")
        return lines

    async def _select_media(self, uri: str, depth: int = 0) -> tuple[str, list[str]]:
        if depth > 2:
            raise SourceError("تداخل قوائم HLS يتجاوز الحد المسموح.")
        lines = await self._playlist(uri)
        if any(line.startswith("#EXT-X-MEDIA:") for line in lines):
            raise SourceError("HLS بمسارات صوت/فيديو منفصلة غير مدعوم؛ استخدم مسار فيديو مدمجًا.")
        for index, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF:"):
                if index + 1 >= len(lines) or lines[index + 1].startswith("#"):
                    raise SourceError("قائمة HLS الرئيسية غير صالحة.")
                return await self._select_media(self._reference(uri, lines[index + 1]), depth + 1)
        return uri, lines

    async def _resource(
        self,
        uri: str,
        *,
        key: bool = False,
        init: bool = False,
        verification_key: bytes | None = None,
        verification_iv: bytes | None = None,
    ) -> str:
        assert self._directory is not None and self._http is not None
        cache_key = (
            ("key\0" if key else "media\0")
            + uri
            + (
                "\0" + hashlib.sha256(verification_key).hexdigest() + (verification_iv or b"").hex()
                if verification_key
                else ""
            )
        )
        if cache_key in self._resources:
            name, size, _ = self._resources[cache_key]
            self._resources[cache_key] = name, size, self._generation
            return name
        suffix = Path(urlsplit(uri).path).suffix.lower()
        if suffix in {".m3u8", ".m3u"}:
            raise SourceError("قائمة HLS فرعية داخل مقطع فيديو غير مسموحة.")
        suffix = (
            ".key"
            if key
            else ".mp4"
            if init
            else suffix
            if suffix in {".ts", ".m4s", ".mp4", ".aac"}
            else ".ts"
        )
        name = hashlib.sha256(cache_key.encode()).hexdigest() + suffix
        data = await self._http.fetch(uri, 16 if key else _SEGMENT_LIMIT)
        if key and len(data) != 16:
            raise SourceError("مفتاح AES-128 غير صالح.")
        if not key:
            await asyncio.to_thread(validate_hls_media, data, verification_key, verification_iv)
        if (
            sum(size for _, size, _ in self._resources.values()) + len(data)
            > settings.HLS_CACHE_MAX_MB * 1024 * 1024
        ):
            raise SourceError(
                "بث HLS يتجاوز حد التخزين المؤقت؛ قلّل دقة/طول القائمة أو استخدم RTSP."
            )
        target = self._directory / name
        temp = target.with_suffix(target.suffix + ".tmp")
        await asyncio.to_thread(temp.write_bytes, data)
        os.replace(temp, target)
        self._resources[cache_key] = name, len(data), self._generation
        return name

    async def _prepare(self, lines: list[str]) -> None:
        assert self._directory is not None
        if not any(line.startswith("#EXTINF:") for line in lines):
            raise SourceError("قائمة HLS بلا مقاطع فيديو مدعومة.")
        if sum(not line.startswith("#") for line in lines) > 64:
            raise SourceError("قائمة HLS تتجاوز 64 مقطعًا؛ استخدم قائمة أقصر أو ملف فيديو.")
        self._generation += 1
        # Keep three previous published generations for a decoder reading behind live edge.
        for uri, (name, _, generation) in list(self._resources.items()):
            if generation < self._generation - 3:
                (self._directory / name).unlink(missing_ok=True)
                del self._resources[uri]
        self._vod = "#EXT-X-ENDLIST" in lines
        rewritten: list[str] = []
        active_key: bytes | None = None
        active_iv: bytes | None = None
        sequence = 0
        try:
            sequences = [
                int(line.split(":", 1)[1])
                for line in lines
                if line.startswith("#EXT-X-MEDIA-SEQUENCE:")
            ]
            if len(sequences) > 1:
                raise ValueError
            sequence = sequences[0] if sequences else 0
            if not 0 <= sequence < 2**128 - 64:
                raise ValueError
        except ValueError:
            raise SourceError("رقم تسلسل HLS غير صالح.") from None
        for line in lines:
            if line.startswith("#EXT-X-TARGETDURATION:"):
                try:
                    duration = float(line.split(":", 1)[1])
                    if not 0 < duration <= 30:
                        raise ValueError
                    self._interval = min(5.0, max(0.5, duration / 2))
                except ValueError:
                    raise SourceError("مدة مقطع HLS غير مدعومة.") from None
            if not line.startswith("#"):
                rewritten.append(
                    await self._resource(
                        self._reference(self._media_uri, line),
                        verification_key=active_key,
                        verification_iv=active_iv or sequence.to_bytes(16, "big"),
                    )
                )
                sequence += 1
                continue
            if line.startswith(("#EXT-X-KEY:", "#EXT-X-MAP:")):
                pairs = _ATTR.findall(line.split(":", 1)[1])
                attrs = {name: value.strip('"') for name, value in pairs}
                key = line.startswith("#EXT-X-KEY:")
                allowed = (
                    {"METHOD", "URI", "IV", "KEYFORMAT", "KEYFORMATVERSIONS"}
                    if key
                    else {"URI", "BYTERANGE"}
                )
                if len(attrs) != len(pairs) or set(attrs) - allowed:
                    raise SourceError("حقول HLS مكررة أو غير مدعومة.")
                if key:
                    if attrs.get("METHOD") == "NONE":
                        active_key, active_iv = None, None
                        rewritten.append("#EXT-X-KEY:METHOD=NONE")
                        continue
                    if (
                        attrs.get("METHOD") != "AES-128"
                        or attrs.get("KEYFORMAT", "identity") != "identity"
                        or attrs.get("KEYFORMATVERSIONS", "1") != "1"
                    ):
                        raise SourceError(
                            "تشفير/DRM HLS هذا غير مدعوم؛ المدعوم AES-128 identity فقط."
                        )
                    try:
                        active_iv = (
                            int(attrs["IV"], 16).to_bytes(16, "big") if "IV" in attrs else None
                        )
                    except (ValueError, OverflowError):
                        raise SourceError("قيمة IV في HLS غير صالحة.") from None
                if len(_URI.findall(line)) != 1:
                    raise SourceError("مرجع مفتاح/تهيئة HLS غير صالح.")
                if not key and active_key and active_iv is None:
                    raise SourceError("تهيئة HLS المشفرة تحتاج IV صريحًا.")
                name = await self._resource(
                    self._reference(self._media_uri, attrs["URI"]),
                    key=key,
                    init=not key,
                    verification_key=active_key if not key else None,
                    verification_iv=active_iv if not key else None,
                )
                if key:
                    active_key = (self._directory / name).read_bytes()
                    line = f'#EXT-X-KEY:METHOD=AES-128,URI="{name}"'
                    if active_iv is not None:
                        line += ",IV=0x" + active_iv.hex()
                else:
                    line = f'#EXT-X-MAP:URI="{name}"'
                    if "BYTERANGE" in attrs:
                        if not re.fullmatch(r"[0-9]+(?:@[0-9]+)?", attrs["BYTERANGE"]):
                            raise SourceError("نطاق تهيئة HLS غير صالح.")
                        line += ',BYTERANGE="' + attrs["BYTERANGE"] + '"'
            elif "URI=" in line or "://" in line:
                raise SourceError("مرجع شبكة HLS غير مدعوم؛ يُرفض بدل تمريره إلى المفكّك.")
            rewritten.append(line)
        playlist = self._directory / "index.m3u8"
        temp = self._directory / "index.tmp"
        await asyncio.to_thread(temp.write_text, "\n".join(rewritten) + "\n", encoding="utf-8")
        os.replace(temp, playlist)

    async def connect(self) -> bool:
        await self.release()
        self.exhausted, self.last_error = False, None
        self._first_pts, self._wall_started, self._last_pts = None, 0.0, 0.0
        self._resources.clear()
        self._generation = 0
        self._directory = Path(tempfile.mkdtemp(prefix="nexora-hls-"))
        self._http = MediaHTTPClient(self.uri, self.auth_mode)
        async with asyncio.timeout(
            settings.HTTP_SOURCE_OPEN_TIMEOUT_SECONDS + settings.HTTP_SOURCE_READ_TIMEOUT_SECONDS
        ):
            self._media_uri, lines = await self._select_media(self.uri)
            await self._prepare(lines)
            self._process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "app.camera.hls_decoder",
                str(self._directory / "index.m3u8"),
                str(settings.HLS_DECODE_FPS),
                str(settings.MAX_IMAGE_PIXELS),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=self.width * self.height * 3 + 65536,
            )
        if not self._vod:
            self._refresh_task = asyncio.create_task(self._refresh(), name="hls-playlist-refresh")
        return True

    async def _refresh(self) -> None:
        try:
            while not self._vod:
                await asyncio.sleep(self._interval)
                async with asyncio.timeout(
                    settings.HTTP_SOURCE_OPEN_TIMEOUT_SECONDS
                    + settings.HTTP_SOURCE_READ_TIMEOUT_SECONDS
                ):
                    await self._prepare(await self._playlist(self._media_uri))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.last_error = "تعذّر تحديث HLS بأمان؛ راجع موارد القائمة وسياسة الشبكة."

    async def read_frame(self) -> np.ndarray | None:
        if self.last_error:
            raise SourceError(self.last_error)
        if self._process is None or self._process.stdout is None:
            return None
        try:
            async with asyncio.timeout(settings.HTTP_SOURCE_READ_TIMEOUT_SECONDS):
                pts = struct.unpack(">d", await self._process.stdout.readexactly(8))[0]
                if not math.isfinite(pts):
                    raise SourceError("توقيت إطار HLS غير صالح.")
                data = await self._process.stdout.readexactly(self.width * self.height * 3)
                if self._first_pts is None or not 0 <= pts - self._last_pts <= 30:
                    self._first_pts, self._wall_started = pts, time.monotonic()
                # Keep temporal PPE rules on media time, not fast VOD decode time.
                delay = pts - self._first_pts - (time.monotonic() - self._wall_started)
                if delay > 0:
                    await asyncio.sleep(delay)
                self._last_pts = pts
            return np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 3).copy()
        except asyncio.IncompleteReadError:
            # Give the process a short opportunity to publish its actual exit code.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._process.wait(), timeout=1.0)
            self.exhausted = self._vod and self._process.returncode == 0
            if not self.exhausted:
                self.last_error = "تعذّر فك فيديو HLS أو انقطع البث."
            return None

    async def release(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            await asyncio.gather(self._refresh_task, return_exceptions=True)
            self._refresh_task = None
        if self._process is not None:

            async def drain():
                if self._process is not None and self._process.stdout is not None:
                    while await self._process.stdout.read(65536):
                        pass

            draining = asyncio.create_task(drain())
            if self._process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2.0)
                except TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            await asyncio.gather(draining, return_exceptions=True)
            self._process = None
        if self._http is not None:
            await self._http.close()
            self._http = None
        if self._directory is not None:
            await asyncio.to_thread(shutil.rmtree, self._directory, True)
            self._directory = None
        self._resources.clear()
