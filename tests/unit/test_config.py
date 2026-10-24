from __future__ import annotations

import pytest

from app.core.config import Settings


def test_industrial_defaults():
    config = Settings(_env_file=None)
    assert config.APP_ENV == "dev"
    assert config.PPE_MODEL_PATH == "Model/ppe.pt"
    assert 0.45 <= config.DETECTION_CONFIDENCE <= 0.55
    assert config.DETECTION_CONFIDENCE == pytest.approx(0.50)
    assert config.CAMERA_CAPTURE_BUFFER_SIZE == 1
    assert config.DB_SQL_ECHO is False
    assert config.ALERT_COOLDOWN_SECONDS == 60
    assert config.VIOLATION_PERSIST_SECONDS == 8
    assert "sqlite" in config.DATABASE_URL
    assert config.MAX_UPLOAD_MB == 100


@pytest.mark.parametrize("value", [0.05, 0.44, 1.1, float("nan")])
def test_confidence_rejects_unsafe_values(value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, DETECTION_CONFIDENCE=value)


@pytest.mark.parametrize(
    "path",
    [
        "Model/unapproved.bin",
        "https://example.invalid/ppe.pt",
        "Model/",
        "",
        "Model/ppe_unified_best.pt",
        "Model/unified/ppe.pt",
        "/srv/weights/PPE_UNIFIED_FINAL.pt",
    ],
)
def test_only_approved_checkpoint_path_is_accepted(path):
    with pytest.raises(ValueError):
        Settings(_env_file=None, PPE_MODEL_PATH=path)


@pytest.mark.parametrize(
    "path", ["Model/ppe_unified_best.pt", "Model/unified/ppe.pt", "ppe_unified_best.pt"]
)
def test_unified_weight_paths_are_rejected_with_the_explicit_message(path):
    with pytest.raises(ValueError, match="unified weights are rejected") as error:
        Settings(_env_file=None, PPE_MODEL_PATH=path)
    assert "Only approved weight Model/ppe.pt is allowed" in str(error.value)


def test_negative_confidence_floor_is_sixty_percent():
    for value in (0.50, 0.55, 0.59):
        with pytest.raises(ValueError):
            Settings(_env_file=None, DETECTION_NEGATIVE_CONFIDENCE=value)
    assert Settings(_env_file=None).DETECTION_NEGATIVE_CONFIDENCE == 0.60


def test_environment_override(monkeypatch):
    monkeypatch.setenv("DETECTION_CONFIDENCE", "0.55")
    assert Settings(_env_file=None).DETECTION_CONFIDENCE == 0.55


@pytest.mark.parametrize(
    "key",
    [
        "CAMERA_CAPTURE_BUFFER_SIZE",
        "VIOLATION_PERSIST_SECONDS",
        "ALERT_COOLDOWN_SECONDS",
        "MAX_UPLOAD_MB",
        "MAX_UPLOAD_VIDEO_SECONDS",
    ],
)
def test_runtime_limits_must_be_positive(key):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{key: 0})


def test_sha256_pin_must_be_valid_hex():
    with pytest.raises(ValueError, match="SHA-256"):
        Settings(_env_file=None, PPE_MODEL_SHA256="not-a-hash")
    assert Settings(_env_file=None, PPE_MODEL_SHA256="a" * 64).PPE_MODEL_SHA256 == "a" * 64
