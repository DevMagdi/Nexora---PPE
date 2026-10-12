from __future__ import annotations

from app.core.config import settings
from app.db.models import Camera


async def test_security_headers_and_no_store_on_api(test_client):
    response = await test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


async def test_untrusted_origin_cannot_perform_state_change(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    response = await anon_client.post(
        "https://test/api/v1/auth/login",
        headers={"Origin": "https://attacker.invalid"},
        data={"username": "user", "password": "not-a-password"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted request origin"


async def test_network_camera_is_denied_by_empty_default_allowlist(test_client, monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "")
    response = await test_client.post(
        "/api/v1/cameras",
        json={
            "name": "untrusted camera",
            "source_type": "rtsp",
            "source_uri": "rtsp://192.168.10.20:554/live",
        },
    )
    assert response.status_code == 400
    assert "configure ALLOWED_RTSP_PREFIXES" in response.json()["detail"]


async def test_camera_source_credentials_are_not_returned_to_frontend(test_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "rtsp://192.168.10.")
    private_uri = "rtsp://camera-user:CameraSecret!@192.168.10.20:554/stream?profile=main"
    response = await test_client.post(
        "/api/v1/cameras",
        json={
            "name": "credentials test",
            "source_type": "rtsp",
            "source_uri": private_uri,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "CameraSecret" not in body["source_uri"]
    assert "camera-user" not in body["source_uri"]
    assert "profile=main" not in body["source_uri"]
    camera = await db_session.get(Camera, body["id"])
    assert camera.source_uri == private_uri
