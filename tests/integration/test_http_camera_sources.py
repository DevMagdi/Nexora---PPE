from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from app.camera.hls_source import HLSSource
from app.camera.http_client import SourceError
from app.camera.mjpeg_source import MJPEGSource
from app.core.config import settings


@dataclass
class MediaServer:
    root: Path
    base: str = ""
    routes: dict[str, tuple[int, dict[str, str], bytes]] = field(default_factory=dict)
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    auth_mode: str | None = None
    refresh_seen: asyncio.Event = field(default_factory=asyncio.Event)

    def authorized(self, headers: dict[str, str]) -> bool:
        value = headers.get("authorization", "")
        if self.auth_mode == "basic":
            return value == "Basic " + base64.b64encode(b"operator:FixtureSecret!").decode()
        if self.auth_mode == "digest":
            parts = {
                name: quoted or plain
                for name, quoted, plain in re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', value)
            }

            def md5(text):
                return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()

            first = md5("operator:PPE:FixtureSecret!")
            second = md5("GET:" + parts.get("uri", ""))
            expected = md5(
                ":".join(
                    [
                        first,
                        "fixture-nonce",
                        parts.get("nc", ""),
                        parts.get("cnonce", ""),
                        "auth",
                        second,
                    ]
                )
            )
            return (
                value.startswith("Digest ")
                and parts.get("username") == "operator"
                and parts.get("response") == expected
            )
        return True


@pytest.fixture
async def media_server(tmp_path, monkeypatch):
    service = MediaServer(tmp_path)
    handlers: set[asyncio.Task] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        task = asyncio.current_task()
        handlers.add(task)
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
            lines = raw.decode("latin-1").split("\r\n")
            path = urlsplit(lines[0].split()[1]).path
            headers = {
                key.lower(): value.strip()
                for line in lines[1:]
                if ":" in line
                for key, value in [line.split(":", 1)]
            }
            service.requests.append((path, headers))
            if sum(p.endswith("playlist.m3u8") for p, _ in service.requests) >= 2:
                service.refresh_seen.set()
            if not service.authorized(headers):
                status, response_headers, body = (
                    401,
                    {
                        "WWW-Authenticate": 'Basic realm="PPE"'
                        if service.auth_mode == "basic"
                        else 'Digest realm="PPE", nonce="fixture-nonce", qop="auth", algorithm=MD5'
                    },
                    b"",
                )
            elif path in service.routes:
                status, response_headers, body = service.routes[path]
            else:
                candidate = (service.root / path.removeprefix("/media/")).resolve()
                if candidate.is_relative_to(service.root) and candidate.is_file():
                    status, response_headers, body = (
                        200,
                        {
                            "Content-Type": "application/vnd.apple.mpegurl"
                            if path.endswith(".m3u8")
                            else "application/octet-stream"
                        },
                        candidate.read_bytes(),
                    )
                else:
                    status, response_headers, body = 404, {}, b""
            head = (
                f"HTTP/1.1 {status} Fixture\r\nContent-Length: {len(body)}\r\nConnection: close\r\n"
            )
            head += "".join(f"{key}: {value}\r\n" for key, value in response_headers.items())
            writer.write((head + "\r\n").encode() + body)
            await writer.drain()
        except (ConnectionError, TimeoutError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    service.base = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/media"
    monkeypatch.setattr(settings, "APP_ENV", "dev")
    monkeypatch.setattr(settings, "ALLOW_LOOPBACK_HTTP_SOURCES", True)
    monkeypatch.setattr(settings, "ALLOWED_HTTP_CAMERA_PREFIXES", service.base)
    try:
        yield service
    finally:
        server.close()
        await server.wait_closed()
        for task in list(handlers):
            task.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)


def generate_hls(root: Path, variant: str) -> None:
    args = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=96x64:rate=12",
        "-t",
        "2",
        "-c:v",
        "libx264",
        "-threads",
        "1",
        "-g",
        "12",
        "-sc_threshold",
        "0",
        "-pix_fmt",
        "yuv420p",
        "-hls_time",
        "1",
        "-hls_list_size",
        "0",
    ]
    if variant == "fmp4":
        args += ["-hls_segment_type", "fmp4"]
    if variant == "aes128":
        (root / "key.key").write_bytes(bytes(range(16)))
        info = root / "keyinfo.txt"
        info.write_text(f"key.key\n{root / 'key.key'}\n")
        args += ["-hls_key_info_file", str(info)]
    args += [
        "-hls_segment_filename",
        str(root / ("part%03d.m4s" if variant == "fmp4" else "part%03d.ts")),
        str(root / "playlist.m3u8"),
    ]
    subprocess.run(args, cwd=root, check=True, capture_output=True, timeout=30)


@pytest.mark.parametrize("variant", ["ts", "fmp4", "aes128"])
async def test_native_hls_decodes_real_http_resources_once_and_cleans_up(media_server, variant):
    await asyncio.to_thread(generate_hls, media_server.root, variant)
    media_server.routes["/media/master.m3u8"] = (
        200,
        {},
        b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=128000\nplaylist.m3u8\n",
    )
    source = HLSSource(media_server.base + "/master.m3u8")
    directory = None
    try:
        assert await source.connect()
        directory = source._directory
        frames = []
        started = time.monotonic()
        async with asyncio.timeout(15):
            while True:
                frame = await source.read_frame()
                if frame is None:
                    break
                frames.append(frame)
        assert time.monotonic() - started >= 1.0  # not an unpaced VOD burst
        assert len(frames) >= 5
        assert frames[0].shape == (540, 960, 3)
        assert frames[0].std() > 5
        assert source.exhausted is True
        assert source.last_error is None
        assert any(path.endswith((".ts", ".m4s")) for path, _ in media_server.requests)
    finally:
        await source.release()
    assert directory is not None and not directory.exists()
    assert source._process is None and source._refresh_task is None


async def test_live_hls_refreshes_and_stop_terminates_decoder_even_with_backpressure(media_server):
    await asyncio.to_thread(generate_hls, media_server.root, "ts")
    path = media_server.root / "playlist.m3u8"
    path.write_text(path.read_text().replace("#EXT-X-ENDLIST", ""))
    source = HLSSource(media_server.base + "/playlist.m3u8")
    try:
        assert await source.connect()
        process, directory = source._process, source._directory
        assert (await source.read_frame()) is not None
        await asyncio.wait_for(media_server.refresh_seen.wait(), timeout=5)
        assert source._refresh_task is not None
        # Stop while FFmpeg may be blocked writing its next raw frame.
        await asyncio.wait_for(source.release(), timeout=5)
        assert process.returncode is not None
        assert not directory.exists()
    finally:
        await source.release()


@pytest.mark.parametrize("auth_mode", ["basic", "digest"])
async def test_mjpeg_reads_multiple_native_jpegs_with_real_http_auth(
    media_server, auth_mode, caplog
):
    media_server.auth_mode = auth_mode
    frame = np.full((36, 64, 3), (30, 80, 140), np.uint8)
    ok, jpeg = cv2.imencode(".jpg", frame)
    assert ok
    part = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
    media_server.routes["/media/video.mjpg"] = (
        200,
        {"Content-Type": "multipart/x-mixed-replace; boundary=frame"},
        part * 3 + b"--frame--\r\n",
    )
    uri = media_server.base.replace("http://", "http://operator:FixtureSecret%21@") + "/video.mjpg"
    source = MJPEGSource(uri, auth_mode)
    try:
        assert await source.connect()
        for _ in range(3):
            decoded = await source.read_frame()
            assert decoded is not None and decoded.shape == frame.shape
        assert await source.read_frame() is None
    finally:
        await source.release()
    assert "FixtureSecret" not in caplog.text and "operator:" not in caplog.text
    assert source._http is None and source._response is None


async def test_mjpeg_rejects_html_and_http_redirect_without_decoder_access(media_server):
    media_server.routes["/media/html"] = (
        200,
        {"Content-Type": "text/html"},
        b"<html>not video</html>",
    )
    media_server.routes["/media/redirect"] = (
        302,
        {"Location": "http://169.254.169.254/latest"},
        b"",
    )
    for path in ["html", "redirect"]:
        source = MJPEGSource(media_server.base + "/" + path)
        try:
            with pytest.raises(SourceError):
                await source.connect()
        finally:
            await source.release()
    assert not any("169.254" in path for path, _ in media_server.requests)
