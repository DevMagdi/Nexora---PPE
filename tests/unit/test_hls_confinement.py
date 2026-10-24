from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.camera.hls_media import validate_hls_media
from app.camera.hls_source import HLSSource
from app.camera.http_client import MediaHTTPClient, SourceError
from app.core.config import settings


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_HTTP_CAMERA_PREFIXES", "http://camera.test/media")
    source = HLSSource("http://camera.test/media/index.m3u8")
    source._directory = tmp_path / "spool"
    source._directory.mkdir()
    source._http = AsyncMock()
    source._http.fetch.return_value = bytes([0x47]) + bytes(187)
    return source


@pytest.mark.parametrize(
    "resource",
    [
        "http://unapproved.test/secret.ts",
        "http://169.254.169.254/latest",
        "file:///etc/passwd",
        "../outside.ts",
        "http://user:secret@camera.test/media/part.ts",
    ],
)
async def test_every_segment_is_policy_checked_before_native_decoder(source, resource):
    with pytest.raises((ValueError, SourceError)):
        await source._prepare(["#EXTM3U", "#EXTINF:1,", resource, "#EXT-X-ENDLIST"])
    source._http.fetch.assert_not_awaited()
    assert not (source._directory / "index.m3u8").exists()


@pytest.mark.parametrize(
    "tag",
    [
        '#EXT-X-KEY:METHOD=AES-128,URI="http://unapproved.test/key"',
        '#EXT-X-MAP:URI="file:///etc/passwd"',
        '#EXT-X-KEY:METHOD=AES-128,URI="key.key",URI="file:///etc/passwd"',
        '#EXT-X-KEY:METHOD=SAMPLE-AES,URI="key.key"',
        '#EXT-X-MAP:URI="init.mp4",UNKNOWN="file:///etc/passwd"',
    ],
)
async def test_keys_init_maps_duplicate_attributes_and_drm_fail_closed(source, tag):
    with pytest.raises((ValueError, SourceError)):
        await source._prepare(["#EXTM3U", tag, "#EXTINF:1,", "one.ts", "#EXT-X-ENDLIST"])
    source._http.fetch.assert_not_awaited()


async def test_native_playlist_contains_only_generated_local_media_paths(source):
    await source._prepare(
        ["#EXTM3U", "#EXT-X-TARGETDURATION:1", "#EXTINF:1,", "one.ts", "#EXT-X-ENDLIST"]
    )
    text = (source._directory / "index.m3u8").read_text()
    assert "http:" not in text and "one.ts" not in text
    paths = [line for line in text.splitlines() if not line.startswith("#")]
    assert len(paths) == 1 and len(paths[0]) == 67
    assert (source._directory / paths[0]).is_file()


@pytest.mark.parametrize(
    "payload",
    [
        b"#EXTM3U\n#EXTINF:1,\nfile:///etc/passwd\n",
        b"<html>not video</html>",
        b"\x00\x00\x00\x08ftypgarbage",
        bytes(376),
    ],
)
def test_segments_cannot_masquerade_as_nested_playlists(payload):
    with pytest.raises(SourceError):
        validate_hls_media(payload)


def test_bmff_external_file_reference_rejected_but_self_contained_allowed():
    def box(kind, body):
        return (8 + len(body)).to_bytes(4, "big") + kind + body

    external = box(b"url ", bytes(4) + b"file:///etc/passwd\0")
    local = box(b"url ", b"\x00\x00\x00\x01")

    def movie(entry):
        return box(b"moov", box(b"dinf", box(b"dref", bytes(4) + (1).to_bytes(4, "big") + entry)))

    validate_hls_media(movie(local))
    with pytest.raises(SourceError):
        validate_hls_media(movie(external))


@pytest.mark.parametrize(
    "feature",
    ['#EXT-X-PART:DURATION=0.2,URI="part.ts"', "#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES"],
)
async def test_ll_hls_is_explicitly_unsupported(source, feature):
    source._http.fetch.return_value = f"#EXTM3U\n{feature}\n#EXTINF:1,\none.ts".encode()
    with pytest.raises(SourceError, match="غير مدعومة"):
        await source._playlist(source.uri)


async def test_http_body_limit_and_stalled_stream_have_finite_bounds(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_HTTP_CAMERA_PREFIXES", "http://camera.test/media")
    monkeypatch.setattr(settings, "HTTP_SOURCE_READ_TIMEOUT_SECONDS", 0.025)

    class Stalled(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"first"
            await asyncio.Event().wait()

    async def handler(request):
        return httpx.Response(200, stream=Stalled())

    client = MediaHTTPClient("http://camera.test/media/index.m3u8")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    monkeypatch.setattr(client, "_addresses", AsyncMock(return_value=["192.168.10.20"]))
    try:
        with pytest.raises(SourceError):
            await client.fetch(client.root_uri, 4)
        with pytest.raises(TimeoutError):
            await client.fetch(client.root_uri, 100)
    finally:
        await client.close()
