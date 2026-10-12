from __future__ import annotations

import secrets

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _production_values() -> dict[str, str]:
    return {
        "APP_ENV": "prod",
        "JWT_SECRET": secrets.token_urlsafe(48),
        "BOOTSTRAP_PASSWORD": "StrongPass!2026-FirstRun",
        "BACKUP_ENCRYPTION_KEY": secrets.token_urlsafe(32),
        "CORS_ORIGINS": "https://nexora.example",
        "ALLOWED_HOSTS": "nexora.example",
        "ALLOWED_RTSP_PREFIXES": "rtsp://192.168.10.,rtsp://10.10.0.",
        "ALLOWED_VIDEO_DIR": "/var/nexora/videos",
        "BACKUP_DIR": "/var/nexora/backups",
    }


def test_valid_production_configuration():
    settings = Settings(_env_file=None, **_production_values())
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 240
    assert settings.cors_origins == ["https://nexora.example"]
    assert settings.allowed_hosts == ["nexora.example"]


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("CORS_ORIGINS", "*", "CORS_ORIGINS"),
        ("CORS_ORIGINS", "https://*.nexora.example", "CORS_ORIGINS"),
        ("ALLOWED_HOSTS", "*", "ALLOWED_HOSTS"),
        ("ALLOWED_HOSTS", "*.nexora.example", "ALLOWED_HOSTS"),
        ("ALLOWED_HOSTS", "https://nexora.example", "ALLOWED_HOSTS"),
        ("CORS_ORIGINS", "https://nexora.example:bad", "CORS origin"),
        ("ALLOWED_RTSP_PREFIXES", "rtsp://192.168.*", "ALLOWED_RTSP_PREFIXES"),
        ("ALLOWED_RTSP_PREFIXES", "rtsp://192.168.10.:bad", "ALLOWED_RTSP_PREFIXES"),
        ("ALLOWED_RTSP_PREFIXES", "", "ALLOWED_RTSP_PREFIXES"),
        ("ALLOWED_VIDEO_DIR", "", "ALLOWED_VIDEO_DIR"),
        ("ALLOWED_VIDEO_DIR", "/", "filesystem root"),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", "1440", "between 60 and 480"),
        ("DB_SQL_ECHO", "true", "DB_SQL_ECHO"),
        ("BOOTSTRAP_PASSWORD", "admin123", "BOOTSTRAP_PASSWORD"),
    ],
)
def test_production_rejects_unsafe_settings(key: str, value: str, message: str):
    values = _production_values()
    values[key] = value
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **values)


def test_production_requires_explicit_secrets():
    values = _production_values()
    values.pop("JWT_SECRET")
    with pytest.raises(ValidationError, match="explicitly configured secrets"):
        Settings(_env_file=None, **values)


def test_production_rejects_http_origin_and_weak_backup_key():
    values = _production_values()
    values["CORS_ORIGINS"] = "http://nexora.example"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)

    values = _production_values()
    values["BACKUP_ENCRYPTION_KEY"] = "not-a-32-byte-key"
    with pytest.raises(ValidationError, match="BACKUP_ENCRYPTION_KEY"):
        Settings(_env_file=None, **values)
