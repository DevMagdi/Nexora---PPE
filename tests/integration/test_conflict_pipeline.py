from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import cv2
import numpy as np
import pytest

from app.camera.manager import CameraManager
from app.core.config import settings
from app.core.detector import Detection
from app.core.ppe import PPE_CLASSES


def evidence(positive=0.68, negative=0.60):
    return [
        Detection(0, "Person", 0.95, 0, 0, 96, 128),
        Detection(1, "Hardhat", positive, 20, 10, 60, 40),
        Detection(2, "NO-Hardhat", negative, 20, 10, 60, 40),
    ]


@pytest.mark.parametrize(
    ("positive", "negative", "expected"), [(0.68, 0.60, "Hardhat"), (0.60, 0.90, "NO-Hardhat")]
)
async def test_image_api_json_and_preview_share_one_decision_and_never_create_events(
    test_client, positive, negative, expected, monkeypatch
):
    detector = test_client._transport.app.state.detector
    detector.detect.return_value = evidence(positive, negative)
    labels = []

    def inspect_label(_frame, text, _position, **_kwargs):
        labels.append(text)

    monkeypatch.setattr("app.core.frame_annotator.draw_text_with_background", inspect_label)
    ok, png = cv2.imencode(".png", np.full((128, 96, 3), 40, np.uint8))
    assert ok
    response = await test_client.post(
        "/api/v1/inference/image",
        files={"file": ("ppe.png", png.tobytes(), "image/png")},
        data={"enabled_classes": "helmet"},
    )
    assert response.status_code == 200
    body = response.json()
    assert [d["class_name"] for d in body["detections"]] == ["Person", expected]
    assert all(d["person_index"] == 0 for d in body["detections"])
    assert len(labels) == 2 and labels[1].startswith(expected + " ")
    assert body["preview"].startswith("data:image/jpeg;base64,")
    assert (await test_client.get("/api/v1/violations")).json()["total"] == 0


async def test_model_meta_disables_missing_negative_vest_but_keeps_positive(test_client):
    detector = test_client._transport.app.state.detector
    detector.class_names = {0: "Person", 1: "Hardhat", 2: "NO-Hardhat", 3: "Safety Vest"}
    for endpoint in ["/api/v1/meta/system", "/api/v1/meta/ppe-classes"]:
        response = await test_client.get(endpoint)
        assert response.status_code == 200
        data = response.json()
        assert data["capabilities_known"] is True
        assert data["supported_negative_rules"] == ["helmet"]
        vest = next(rule for rule in data.get("rules", data.get("items")) if rule["key"] == "vest")
        assert vest["positive_supported"] is True and vest["negative_supported"] is False
    data = (await test_client.get("/api/v1/meta/system")).json()
    assert data["platform_name"] == "Mantik PPE"
    assert data["negative_confidence"] == 0.60
    assert data["effective_negative_confidence"] == 0.60
    assert data["conflict_policy"]["negative_clear_margin"] == 0.15
    # Positive vest selection remains an actual image display option.
    detector.detect.return_value = [Detection(3, "Safety Vest", 0.9, 10, 20, 40, 60)]
    _, png = cv2.imencode(".png", np.zeros((128, 96, 3), np.uint8))
    image = await test_client.post(
        "/api/v1/inference/image",
        files={"file": ("vest.png", png.tobytes(), "image/png")},
        data={"enabled_classes": "vest"},
    )
    assert [d["class_name"] for d in image.json()["detections"]] == ["Safety Vest"]


async def test_unknown_checkpoint_metadata_is_not_presented_as_verified_capabilities(test_client):
    data = (await test_client.get("/api/v1/meta/system")).json()
    assert data["capabilities_known"] is False
    assert data["supported_negative_rules"] is None


@pytest.mark.parametrize(
    ("positive", "negative", "violation_expected"), [(0.68, 0.60, False), (0.60, 0.90, True)]
)
async def test_native_file_pipeline_uses_resolved_counts_and_sustained_evidence(
    tmp_path, monkeypatch, positive, negative, violation_expected
):
    """Native video reader; explicitly synthetic detector and clock, not ML validation."""
    path = tmp_path / "fixture.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 20, (96, 128))
    assert writer.isOpened()
    for _ in range(12):
        writer.write(np.zeros((128, 96, 3), np.uint8))
    writer.release()
    clock = [100.0]

    class DetectorDouble:
        supported_negative_rules = frozenset(PPE_CLASSES)

        def detect(self, _frame):
            clock[0] += 1
            return evidence(positive, negative)

    monkeypatch.setattr(settings, "ALLOWED_VIDEO_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.core.violation_checker.time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    manager = CameraManager(DetectorDouble())
    monkeypatch.setattr(manager, "_mark_inactive", AsyncMock())
    handle = AsyncMock()
    monkeypatch.setattr(manager, "_handle_violations", handle)
    try:
        assert await manager.start_camera(123, "file", str(path), ["helmet"])
        entry = manager._entries[123]
        await entry.task
        assert manager.get_connection_status(123) == "completed"
        assert entry.latest_counts["person"] == 1
        assert entry.latest_counts["hardhat"] == (0 if violation_expected else 1)
        assert entry.latest_counts["no_hardhat"] == (1 if violation_expected else 0)
        assert handle.await_count == (1 if violation_expected else 0)
        if violation_expected:
            assert handle.await_args.args[1][0].violation_type == "NO-Hardhat"
    finally:
        await manager.stop()


async def test_meta_distinguishes_configured_and_effective_negative_threshold(
    test_client, monkeypatch
):
    monkeypatch.setattr(settings, "DETECTION_CONFIDENCE", 0.85)
    data = (await test_client.get("/api/v1/meta/system")).json()
    assert data["confidence"] == 0.85
    assert data["negative_confidence"] == 0.60
    assert data["effective_negative_confidence"] == 0.85
