from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.config import settings
from app.core.detector import Detection
from app.db.models import Camera


def image_bytes():
    ok, image = cv2.imencode(".png", np.full((64, 96, 3), 40, dtype=np.uint8))
    assert ok
    return image.tobytes()


@pytest.fixture
def video_bytes(tmp_path):
    path = tmp_path / "fixture.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(20):
        writer.write(np.full((48, 64, 3), 40, dtype=np.uint8))
    writer.release()
    return path.read_bytes()


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    root = tmp_path / "videos"
    root.mkdir()
    monkeypatch.setattr(settings, "ALLOWED_VIDEO_DIR", str(root))
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(root / "uploads"))
    return root


async def test_image_upload_uses_shared_detector_and_selected_rules(test_client):
    detector = test_client._transport.app.state.detector
    detector.detect.return_value = [
        Detection(0, "NO-Hardhat", 0.9, 1, 1, 20, 20),
        Detection(1, "NO-Gloves", 0.9, 1, 1, 20, 20),
    ]
    response = await test_client.post(
        "/api/v1/inference/image",
        files={"file": ("gate.png", image_bytes(), "image/png")},
        data={"enabled_classes": "helmet"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["width"] == 96 and data["height"] == 64
    assert data["preview"].startswith("data:image/jpeg;base64,")
    assert [item["class_name"] for item in data["detections"]] == ["NO-Hardhat"]
    detector.detect.assert_called_once()
    assert (await test_client.get("/api/v1/violations")).json()["total"] == 0


@pytest.mark.parametrize(
    ("filename", "contents", "rules"),
    [
        ("bad.jpg", b"corrupt", "helmet"),
        ("empty.png", b"", "helmet"),
        ("ok.png", image_bytes(), "unknown"),
        ("ok.png", image_bytes(), ""),
    ],
    ids=["corrupt", "empty", "unknown-rule", "empty-rules"],
)
async def test_invalid_image_or_rule_is_rejected(test_client, filename, contents, rules):
    response = await test_client.post(
        "/api/v1/inference/image",
        files={"file": (filename, contents, "image/png")},
        data={"enabled_classes": rules},
    )
    assert response.status_code == 422


async def test_image_pixel_limit_prevents_decode(test_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_IMAGE_PIXELS", 100)
    response = await test_client.post(
        "/api/v1/inference/image", files={"file": ("gate.png", image_bytes(), "image/png")}
    )
    assert response.status_code == 422
    test_client._transport.app.state.detector.detect.assert_not_called()


async def test_oversized_file_and_content_length_are_rejected(test_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    response = await test_client.post(
        "/api/v1/inference/image",
        files={"file": ("large.png", b"x" * (1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413
    response = await test_client.post(
        "/api/v1/inference/image", content=b"x", headers={"Content-Length": str(2 * 1024 * 1024)}
    )
    assert response.status_code == 413
    response = await test_client.post(
        "/api/v1/inference/image", content=b"x", headers={"Content-Length": "invalid"}
    )
    assert response.status_code == 400


async def test_chunked_multipart_body_is_limited_before_spooling(test_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

    async def body():
        yield b'--nexora\r\nContent-Disposition: form-data; name="file"; filename="large.png"\r\nContent-Type: image/png\r\n\r\n'
        for _ in range(20):
            yield b"x" * (64 * 1024)
        yield b"\r\n--nexora--\r\n"

    response = await test_client.post(
        "/api/v1/inference/image",
        content=body(),
        headers={"Content-Type": "multipart/form-data; boundary=nexora"},
    )
    assert response.status_code == 413


async def test_video_upload_registers_a_confined_source(
    test_client, db_session, uploads, video_bytes
):
    response = await test_client.post(
        "/api/v1/inference/video",
        files={"file": ("../../outside.avi", video_bytes, "video/x-msvideo")},
        data={"name": "Loading dock", "enabled_classes": "helmet,vest"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "file" and not data["is_running"]
    assert str(uploads) not in data["source_uri"]
    camera = await db_session.get(Camera, data["id"])
    path = Path(camera.source_uri)
    assert path.is_relative_to(uploads / "uploads")
    assert path.name != "outside.avi" and path.is_file()
    assert (await test_client.post(f"/api/v1/cameras/{data['id']}/start")).status_code == 200


@pytest.mark.parametrize(
    ("filename", "contents"),
    [("bad.avi", b"bad video"), ("empty.mp4", b""), ("unknown.exe", b"fixture")],
)
async def test_invalid_video_is_rejected_and_cleaned(test_client, uploads, filename, contents):
    response = await test_client.post(
        "/api/v1/inference/video",
        files={"file": (filename, contents, "application/octet-stream")},
        data={"name": "Gate"},
    )
    assert response.status_code == 422
    assert list((uploads / "uploads").glob("*")) == []


async def test_video_duration_limit_and_disabled_upload_root(
    test_client, uploads, video_bytes, monkeypatch
):
    monkeypatch.setattr(settings, "MAX_UPLOAD_VIDEO_SECONDS", 1)
    response = await test_client.post(
        "/api/v1/inference/video",
        files={"file": ("long.avi", video_bytes, "video/x-msvideo")},
        data={"name": "Gate"},
    )
    assert response.status_code == 422
    assert not list((uploads / "uploads").glob("*"))
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(uploads.parent / "outside"))
    response = await test_client.post(
        "/api/v1/inference/video",
        files={"file": ("gate.avi", video_bytes, "video/x-msvideo")},
        data={"name": "Gate"},
    )
    assert response.status_code == 503


async def test_upload_endpoints_require_authentication(anon_client):
    for endpoint in ["image", "video"]:
        response = await anon_client.post(
            f"/api/v1/inference/{endpoint}",
            files={"file": ("gate.png", image_bytes(), "image/png")},
            data={"name": "Gate"},
        )
        assert response.status_code == 401


async def test_video_commit_failure_rolls_back_and_removes_uncommitted_upload(
    test_client, db_session, video_bytes, uploads, monkeypatch
):
    from unittest.mock import AsyncMock

    from sqlalchemy import func, select

    rollback = AsyncMock(wraps=db_session.rollback)
    monkeypatch.setattr(db_session, "rollback", rollback)
    monkeypatch.setattr(
        db_session, "commit", AsyncMock(side_effect=RuntimeError("test-only commit failure"))
    )
    with pytest.raises(RuntimeError, match="test-only commit failure"):
        await test_client.post(
            "/api/v1/inference/video",
            files={"file": ("bay.avi", video_bytes, "video/x-msvideo")},
            data={"name": "Commit failure"},
        )
    rollback.assert_awaited_once()
    assert not list((uploads / "uploads").glob("*"))
    assert (await db_session.execute(select(func.count(Camera.id)))).scalar_one() == 0


async def test_post_commit_refresh_failure_does_not_orphan_registered_video(
    test_client, db_session, video_bytes, uploads, monkeypatch
):
    from unittest.mock import AsyncMock

    from sqlalchemy import select

    monkeypatch.setattr(
        db_session, "refresh", AsyncMock(side_effect=RuntimeError("test-only refresh failure"))
    )
    with pytest.raises(RuntimeError, match="test-only refresh failure"):
        await test_client.post(
            "/api/v1/inference/video",
            files={"file": ("bay.avi", video_bytes, "video/x-msvideo")},
            data={"name": "Durable uploaded video"},
        )
    camera = (await db_session.execute(select(Camera))).scalar_one()
    assert camera.name == "Durable uploaded video"
    assert Path(camera.source_uri).is_file()
    assert len(list((uploads / "uploads").glob("*.avi"))) == 1
