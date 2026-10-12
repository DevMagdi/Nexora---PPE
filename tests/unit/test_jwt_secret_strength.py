"""JWT secret strength: fail fast on weak HS256 keys in every environment.

Regression tests for the local-run log of 2026-10-12, where a 22-byte
JWT_SECRET only surfaced as a cryptic PyJWT InsecureKeyLengthWarning at the
first login instead of a clear startup error.
"""

from __future__ import annotations

import secrets

import pytest
from pydantic import ValidationError

from app.core.config import Settings, jwt_secret_issues


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


def test_jwt_secret_issues_detects_short_key():
    issues = jwt_secret_issues("my-dev-secret-12345")  # 19 bytes, like the reported log
    assert issues
    assert any("bytes long" in issue for issue in issues)


def test_jwt_secret_issues_detects_low_entropy_key():
    assert jwt_secret_issues("a" * 64)  # long enough but not random
    assert jwt_secret_issues(secrets.token_urlsafe(48)) == []


@pytest.mark.parametrize("env", ["dev", "staging"])
def test_explicit_weak_jwt_secret_rejected_outside_prod(env: str):
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, APP_ENV=env, JWT_SECRET="my-dev-secret-12345")


def test_explicit_weak_jwt_secret_rejected_in_prod():
    values = _production_values()
    values["JWT_SECRET"] = "my-dev-secret-12345"
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, **values)


def test_weak_jwt_secret_from_env_rejected(monkeypatch):
    # The exact reported scenario: a short value coming from the environment/.env.
    monkeypatch.setenv("JWT_SECRET", "my-dev-secret-12345")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None)


def test_default_random_secret_accepted_in_dev():
    settings = Settings(_env_file=None)
    assert jwt_secret_issues(settings.JWT_SECRET) == []


def test_explicit_strong_secret_accepted(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    settings = Settings(_env_file=None)
    assert jwt_secret_issues(settings.JWT_SECRET) == []


def test_gen_script_refuses_short_lengths():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/gen_jwt_secret.py", "--bytes", "16"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "32 bytes" in proc.stderr


def _import_auth():
    try:
        from app.core import auth

        return auth
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on installed extras
        pytest.skip(f"web dependencies are not installed: {exc}")


def test_auth_guard_fails_closed_on_weak_secret(monkeypatch):
    auth = _import_auth()
    monkeypatch.setattr(auth.settings, "JWT_SECRET", "too-short")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        auth.ensure_jwt_secret_strength()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        auth.create_access_token("1")


def test_auth_guard_passes_on_strong_secret(monkeypatch):
    auth = _import_auth()
    monkeypatch.setattr(auth.settings, "JWT_SECRET", secrets.token_urlsafe(48))
    auth.ensure_jwt_secret_strength()  # must not raise
