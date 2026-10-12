from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from app.core import auth


def test_new_password_hash_uses_a_high_work_factor():
    password_hash = auth.hash_password("Strong!Password2026")
    assert password_hash.startswith("$pbkdf2-sha256$600000$")
    assert auth.verify_password("Strong!Password2026", password_hash)


def test_access_and_media_tokens_are_type_separated(monkeypatch):
    access = auth.create_access_token("17", token_version=3)
    media = auth.create_access_token("17", token_type="media", token_version=3)
    assert auth.decode_token_payload(access, "access")["sub"] == "17"
    assert auth.decode_token_payload(media, "media")["sub"] == "17"
    with pytest.raises(HTTPException):
        auth.decode_token_payload(access, "media")
    with pytest.raises(HTTPException):
        auth.decode_token_payload(media, "access")


def test_expired_and_malformed_tokens_are_rejected():
    expired = auth.jwt.encode(
        {
            "sub": "17",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "token_type": "access",
            "ver": 0,
        },
        auth.settings.JWT_SECRET,
        algorithm=auth.settings.JWT_ALGORITHM,
    )
    for token in (expired, "not-a-jwt"):
        with pytest.raises(HTTPException):
            auth.decode_token_payload(token)


def test_production_cookies_are_host_only_secure_and_httponly(monkeypatch):
    monkeypatch.setattr(auth.settings, "APP_ENV", "prod")
    user = SimpleNamespace(id=17, token_version=2)
    response = Response()
    auth.set_session_cookies(response, user)

    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    assert any("__Host-nexora_access=" in cookie for cookie in cookies)
    assert any("__Host-nexora_media=" in cookie for cookie in cookies)
    for cookie in cookies:
        assert "Secure" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/" in cookie
        assert "Domain=" not in cookie
