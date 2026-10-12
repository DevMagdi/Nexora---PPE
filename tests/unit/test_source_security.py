from __future__ import annotations

import pytest

from app.camera.source_security import validate_camera_source, validate_file_uri, validate_rtsp_uri
from app.core.config import settings


def test_rtsp_allowlist_matches_only_configured_ip_prefix(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "rtsp://192.168.10.,rtsps://10.10.0.")
    validate_rtsp_uri("rtsp://192.168.10.23:554/stream")
    validate_rtsp_uri("rtsps://10.10.0.9/live")

    with pytest.raises(ValueError, match="outside"):
        validate_rtsp_uri("rtsp://192.168.100.23/stream")
    with pytest.raises(ValueError, match="outside"):
        validate_rtsp_uri("rtsp://192.168.10.attacker.invalid/stream")


def test_rtsp_allowlist_restricts_ports_to_standard_or_explicit_port(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "rtsp://192.168.10.")
    validate_rtsp_uri("rtsp://192.168.10.25/live")
    validate_rtsp_uri("rtsp://192.168.10.25:554/live")
    with pytest.raises(ValueError, match="outside"):
        validate_rtsp_uri("rtsp://192.168.10.25:8554/live")

    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "rtsp://192.168.10.:8554")
    validate_rtsp_uri("rtsp://192.168.10.25:8554/live")
    with pytest.raises(ValueError, match="outside"):
        validate_rtsp_uri("rtsp://192.168.10.25:554/live")


def test_rtsp_blocks_open_defaults_and_local_metadata(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "")
    with pytest.raises(ValueError, match="disabled"):
        validate_rtsp_uri("rtsp://192.168.10.23/stream")

    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "http://127.0.0.1,http://169.254.169.254")
    for uri in (
        "http://127.0.0.1/latest/meta-data/",
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost/admin",
        "file:///etc/passwd",
        "http://192.168.10.4/path?access_token=secret",
    ):
        with pytest.raises(ValueError):
            validate_rtsp_uri(uri)


def test_file_sources_are_confined_to_configured_directory(tmp_path, monkeypatch):
    allowed = tmp_path / "videos"
    allowed.mkdir()
    clip = allowed / "clip.mp4"
    clip.write_bytes(b"not a real video; path validation only")
    secret = tmp_path / "secret.mp4"
    secret.write_bytes(b"secret")
    (allowed / "outside.mp4").symlink_to(secret)
    monkeypatch.setattr(settings, "ALLOWED_VIDEO_DIR", str(allowed))

    assert validate_file_uri("clip.mp4") == str(clip)
    assert validate_camera_source("file", str(clip)) == str(clip)
    with pytest.raises(ValueError, match="outside"):
        validate_file_uri("../secret.mp4")
    with pytest.raises(ValueError, match="outside"):
        validate_file_uri("outside.mp4")
    with pytest.raises(ValueError, match="exist"):
        validate_file_uri("missing.mp4")


def test_file_sources_are_disabled_without_directory(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_VIDEO_DIR", "")
    with pytest.raises(ValueError, match="disabled"):
        validate_file_uri("clip.mp4")


def test_webcam_validation_rejects_negative_and_non_integer():
    assert validate_camera_source("webcam", "0") == "0"
    for value in ("-1", "0; rm -rf /", "not-a-number"):
        with pytest.raises(ValueError):
            validate_camera_source("webcam", value)
