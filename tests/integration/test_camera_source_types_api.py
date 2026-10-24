from __future__ import annotations

import json
from urllib.parse import unquote, urlsplit

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models import AuditLog, Camera


@pytest.fixture
def typed_policy(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ALLOWED_RTSP_PREFIXES", "rtsp://192.168.10.,rtsps://192.168.10.")
    monkeypatch.setattr(
        settings,
        "ALLOWED_HTTP_CAMERA_PREFIXES",
        "http://192.168.10.20:8080/media,https://192.168.10.20/media",
    )
    monkeypatch.setattr(settings, "ALLOWED_VIDEO_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ENABLE_USB_SOURCES", True)
    monkeypatch.setattr(settings, "APP_ENV", "dev")
    monkeypatch.setattr(settings, "ALLOWED_USB_DEVICE_INDICES", "0,1")
    (tmp_path / "test.mp4").write_bytes(
        b"API registration only; real decoding is tested separately"
    )
    return tmp_path


@pytest.mark.parametrize(
    "source",
    [
        {"source_type": "rtsp", "source_uri": "rtsp://192.168.10.20/live", "port": 554},
        {"source_type": "rtsps", "source_uri": "rtsps://192.168.10.20/live", "port": 322},
        {
            "source_type": "http_mjpeg",
            "source_uri": "http://192.168.10.20/media/video.mjpg",
            "port": 8080,
        },
        {
            "source_type": "hls",
            "source_uri": "https://192.168.10.20/media/index.m3u8",
            "auth_mode": "digest",
        },
        {"source_type": "file", "source_uri": "test.mp4"},
        {"source_type": "usb", "device_index": 1},
    ],
)
async def test_each_type_registers_with_distinct_suitable_fields(test_client, typed_policy, source):
    result = await test_client.post("/api/v1/cameras", json={"name": "Typed source", **source})
    assert result.status_code == 201, result.text
    camera = result.json()
    assert camera["source_type"] == source["source_type"]
    assert camera["connection_status"] == "stopped"
    assert camera["last_error"] is None and not camera["is_running"]
    if source["source_type"] == "usb":
        assert camera["device_index"] == 1
    if "port" in source:
        assert camera["port"] == source["port"]


async def test_network_passwords_are_write_only_and_never_copied_to_replacement_uri(
    test_client, db_session, typed_policy
):
    result = await test_client.post(
        "/api/v1/cameras",
        json={
            "name": "Private stream",
            "source_type": "http_mjpeg",
            "source_uri": "http://192.168.10.20:8080/media/video.mjpg",
            "source_username": "private-operator",
            "source_password": "OriginalPrivateValue!",
            "auth_mode": "digest",
        },
    )
    assert result.status_code == 201
    camera_id = result.json()["id"]
    camera = await db_session.get(Camera, camera_id)
    assert unquote(urlsplit(camera.source_uri).password) == "OriginalPrivateValue!"
    for response in [
        result,
        await test_client.get("/api/v1/cameras"),
        await test_client.get(f"/api/v1/cameras/{camera_id}"),
    ]:
        assert (
            "OriginalPrivateValue" not in response.text and "private-operator" not in response.text
        )
        assert "source_password" not in response.text and "source_username" not in response.text
    replacement = await test_client.put(
        f"/api/v1/cameras/{camera_id}",
        json={"source_uri": "http://192.168.10.20:8080/media/new.mjpg"},
    )
    assert replacement.status_code == 200
    await db_session.refresh(camera)
    assert urlsplit(camera.source_uri).username is None
    update = await test_client.put(
        f"/api/v1/cameras/{camera_id}",
        json={"source_username": "new-operator", "source_password": "SecondPrivateValue!"},
    )
    assert update.status_code == 200 and "SecondPrivateValue" not in update.text
    cleared = await test_client.put(
        f"/api/v1/cameras/{camera_id}", json={"clear_credentials": True}
    )
    assert cleared.status_code == 200
    await db_session.refresh(camera)
    assert urlsplit(camera.source_uri).username is None
    audit = (await db_session.scalars(select(AuditLog))).all()
    details = json.dumps([row.details for row in audit])
    assert "PrivateValue" not in details and "new-operator" not in details


@pytest.mark.parametrize(
    "source",
    [
        {"source_type": "hls", "source_uri": "rtsp://192.168.10.20/live"},
        {"source_type": "http_mjpeg", "source_uri": "https://192.168.10.20/media/index.m3u8"},
        {"source_type": "rtsp", "source_uri": "rtsps://192.168.10.20/live"},
        {"source_type": "hls", "source_uri": "https://192.168.10.20/media/video.mjpg"},
        {"source_type": "rtsp", "source_uri": "rtsp://192.168.10.20:554/live", "port": 8554},
        {"source_type": "file", "source_uri": "test.mp4", "source_password": "MustNotBeStored"},
        {"source_type": "usb", "device_index": 2},
        {"source_type": "usb", "device_index": 0, "source_uri": "0"},
    ],
)
async def test_incompatible_source_fields_are_rejected(test_client, typed_policy, source):
    result = await test_client.post("/api/v1/cameras", json={"name": "Rejected source", **source})
    assert result.status_code in {400, 422}, result.text


@pytest.mark.parametrize("env,enabled", [("prod", True), ("staging", True), ("dev", False)])
async def test_usb_registration_is_not_a_production_capability(
    test_client, typed_policy, monkeypatch, env, enabled
):
    monkeypatch.setattr(settings, "APP_ENV", env)
    monkeypatch.setattr(settings, "ENABLE_USB_SOURCES", enabled)
    response = await test_client.post(
        "https://test/api/v1/cameras", json={"name": "USB", "source_type": "usb", "device_index": 0}
    )
    assert response.status_code == 400


async def test_type_alias_onvif_metadata_and_controlled_type_change(
    test_client, typed_policy, db_session
):
    device = "http://192.168.10.20:8080/media/onvif/device_service"
    result = await test_client.post(
        "/api/v1/cameras",
        json={
            "name": "Metadata",
            "type": "rtsp",
            "source_uri": "rtsp://192.168.10.20/live",
            "onvif_device_uri": device,
        },
    )
    assert result.status_code == 201
    assert result.json()["onvif_device_uri"] == device
    camera_id = result.json()["id"]
    # A changed kind may not inherit an incompatible private URI.
    invalid = await test_client.put(f"/api/v1/cameras/{camera_id}", json={"source_type": "hls"})
    assert invalid.status_code == 400
    updated = await test_client.put(
        f"/api/v1/cameras/{camera_id}", json={"source_type": "usb", "device_index": 1}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["onvif_device_uri"] is None
    assert updated.json()["source_type"] == "usb"
    test_client._transport.app.state.camera_manager.stop_camera.assert_awaited_once_with(camera_id)


async def test_start_failure_is_persisted_without_native_exception_credentials(
    test_client, typed_policy, db_session
):
    camera = (
        await test_client.post(
            "/api/v1/cameras",
            json={"name": "Fail", "source_type": "rtsp", "source_uri": "rtsp://192.168.10.20/live"},
        )
    ).json()
    manager = test_client._transport.app.state.camera_manager
    manager.start_camera.side_effect = ValueError(
        "Native exception with rtsp://user:NeverReturnThis@192.168.10.20/live"
    )
    response = await test_client.post(f"/api/v1/cameras/{camera['id']}/start")
    assert response.status_code == 400
    stored = await db_session.get(Camera, camera["id"])
    assert stored.last_error and not stored.is_active
    listed = await test_client.get(f"/api/v1/cameras/{camera['id']}")
    assert listed.json()["connection_status"] == "error"
    assert "NeverReturnThis" not in response.text + listed.text


async def test_system_meta_does_not_advertise_discovery_or_production_usb(
    test_client, typed_policy, monkeypatch
):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    body = (await test_client.get("https://test/api/v1/meta/system")).json()
    assert body["supported_source_types"] == ["rtsp", "rtsps", "http_mjpeg", "hls", "file", "usb"]
    assert body["recommended_source_type"] == "rtsp"
    assert body["onvif_mode"] == "metadata_only"
    assert not body["usb_sources_enabled"] and not body["usb_device_indices"]
