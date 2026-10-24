from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.camera.http_client import MediaHTTPClient, SourceError
from app.camera.source_security import (
    validate_camera_source,
    validate_http_uri,
    validate_onvif_device_uri,
)
from app.core.config import Settings, settings


@pytest.fixture
def http_policy(monkeypatch):
    monkeypatch.setattr(
        settings,
        "ALLOWED_HTTP_CAMERA_PREFIXES",
        "http://camera.test/media,https://camera.test/media,http://cdn.test/assets",
    )
    monkeypatch.setattr(settings, "ALLOW_LOOPBACK_HTTP_SOURCES", False)


@pytest.mark.parametrize(
    "kind,uri",
    [
        ("rtsp", "rtsps://192.168.10.20/live"),
        ("rtsps", "rtsp://192.168.10.20/live"),
        ("hls", "rtsp://192.168.10.20/live"),
        ("hls", "http://camera.test/media/video.mjpg"),
        ("http_mjpeg", "http://camera.test/media/index.m3u8"),
    ],
)
def test_type_and_protocol_cannot_be_confused(http_policy, kind, uri):
    with pytest.raises(ValueError):
        validate_camera_source(kind, uri)


@pytest.mark.parametrize(
    "uri",
    [
        "http://camera.test.evil/media/video.mjpg",
        "http://camera.test:8888/media/video.mjpg",
        "http://camera.test/media-escape/video.mjpg",
        "http://camera.test/media/../admin",
        "http://camera.test/media/%2e%2e/admin",
        "http://camera.test/media/%252e%252e/admin",
        "http://camera.test/media/index.m3u8?password=secret",
        "http://camera.test/media/a#fragment",
        "http://169.254.169.254/media",
        "http://127.0.0.1/media",
        "http://[::1]/media",
        "file:///etc/passwd",
        "http://metadata.google.internal/media",
    ],
)
def test_http_policy_rejects_network_and_path_escapes(http_policy, uri):
    with pytest.raises(ValueError):
        validate_http_uri(uri)


def test_empty_http_allowlist_is_closed(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_HTTP_CAMERA_PREFIXES", "")
    with pytest.raises(ValueError, match="ALLOWED_HTTP_CAMERA_PREFIXES"):
        validate_http_uri("http://192.168.10.20/video.mjpg")


async def test_dns_is_pinned_with_original_host_and_no_cross_origin_credentials(
    http_policy, monkeypatch
):
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, content=b"segment")

    client = MediaHTTPClient("http://user:SensitiveValue@camera.test/media/index.m3u8")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    monkeypatch.setattr(client, "_addresses", AsyncMock(return_value=["192.168.10.20"]))
    try:
        assert await client.fetch("http://camera.test/media/one.ts", 100) == b"segment"
        assert await client.fetch("http://cdn.test/assets/two.ts", 100) == b"segment"
        assert requests[0].url.host == "192.168.10.20"
        assert requests[0].headers["host"] == "camera.test"
        assert requests[0].extensions["sni_hostname"] == "camera.test"
        assert requests[0].headers["authorization"].startswith("Basic ")
        assert "authorization" not in requests[1].headers
        assert "user" not in str(requests[0].url)
    finally:
        await client.close()


async def test_all_dns_answers_checked_before_connecting(http_policy, monkeypatch):
    client = MediaHTTPClient("http://camera.test/media/live.mjpg")
    monkeypatch.setattr(
        client, "_addresses", AsyncMock(return_value=["192.168.10.20", "127.0.0.1"])
    )
    send = AsyncMock()
    monkeypatch.setattr(client.client, "send", send)
    try:
        with pytest.raises(ValueError, match="Loopback"):
            await client.open(client.root_uri)
        send.assert_not_called()
    finally:
        await client.close()


async def test_redirects_are_closed_not_followed(http_policy, monkeypatch):
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    client = MediaHTTPClient("http://camera.test/media/a.m3u8")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    monkeypatch.setattr(client, "_addresses", AsyncMock(return_value=["192.168.10.20"]))
    try:
        with pytest.raises(SourceError, match="توجيه"):
            await client.open(client.root_uri)
        assert len(requests) == 1
    finally:
        await client.close()


def test_onvif_is_only_controlled_noncredential_metadata(http_policy):
    assert validate_onvif_device_uri("http://camera.test/media/onvif/device_service", "rtsp")
    for uri in [
        "http://user:secret@camera.test/media/onvif",
        "http://camera.test/media/onvif?token=a",
    ]:
        with pytest.raises(ValueError):
            validate_onvif_device_uri(uri, "rtsp")
    with pytest.raises(ValueError):
        validate_onvif_device_uri("http://camera.test/media/onvif", "file")


@pytest.mark.parametrize("env", ["staging", "prod"])
@pytest.mark.parametrize("flag", ["ENABLE_USB_SOURCES", "ALLOW_LOOPBACK_HTTP_SOURCES"])
def test_development_source_flags_fail_outside_dev(env, flag):
    with pytest.raises(ValueError, match="development-only"):
        Settings(_env_file=None, APP_ENV=env, **{flag: True})


def test_http_dns_name_is_exact_even_with_trailing_root_dot(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_HTTP_CAMERA_PREFIXES", "http://camera.test.")
    validate_http_uri("http://camera.test/media/video.mjpg")
    with pytest.raises(ValueError):
        validate_http_uri("http://camera.test.evil/media/video.mjpg")


def test_excessive_path_encoding_fails_closed(http_policy):
    with pytest.raises(ValueError):
        validate_http_uri("http://camera.test/media/%252525252e%252525252e/secret")


@pytest.mark.parametrize(
    "address", ["0.0.0.1", "100.100.100.200", "168.63.129.16", "fd00:ec2::254"]
)
def test_known_metadata_and_current_network_addresses_are_always_forbidden(address):
    from app.camera.source_security import validate_resolved_address

    with pytest.raises(ValueError):
        validate_resolved_address(address, http=True)
