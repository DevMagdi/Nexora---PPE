from __future__ import annotations

import pytest

from app.core.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.APP_ENV == "dev"
    assert s.CONSTRUCTION_MODEL_PATH == "Model/ppe.pt"
    assert s.MEDICAL_MODEL_PATH == "Model/bestMedicalModel.pt"
    assert s.CONSTRUCTION_DETECTION_CONFIDENCE == pytest.approx(0.10)
    assert s.MEDICAL_DETECTION_CONFIDENCE == pytest.approx(0.15)
    assert s.ALERT_COOLDOWN_SECONDS == 60


def test_hybrid_and_skin_defaults():
    s = Settings(_env_file=None)
    assert s.HYBRID_DETECTION_ENABLED is True
    assert s.HYBRID_CONSTRUCTION_ON_MEDICAL is True
    assert s.HYBRID_MEDICAL_ON_CONSTRUCTION is False
    assert s.SKIN_FILTER_ENABLED is True
    assert s.SKIN_BARE_HAND_ENABLED is True
    assert s.SKIN_EYE_BRIDGE_ENABLED is True
    assert 0.0 < s.SKIN_MIN_RATIO < s.SKIN_STRONG_RATIO < 1.0
    assert s.SKIN_BARE_HAND_MIN_THICKNESS == pytest.approx(0.12)
    assert s.SKIN_EYE_BRIDGE_MIN_SKIN_RATIO == pytest.approx(0.22)


def test_hybrid_can_be_disabled_by_env(monkeypatch):
    monkeypatch.setenv("HYBRID_DETECTION_ENABLED", "false")
    monkeypatch.setenv("SKIN_FILTER_ENABLED", "false")
    monkeypatch.setenv("MEDICAL_MODEL_PATH", "Model/custom.pt")
    s = Settings(_env_file=None)
    assert s.HYBRID_DETECTION_ENABLED is False
    assert s.SKIN_FILTER_ENABLED is False
    assert s.MEDICAL_MODEL_PATH == "Model/custom.pt"


def test_env_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("CONSTRUCTION_DETECTION_CONFIDENCE", "0.7")
    monkeypatch.setenv("ALERT_COOLDOWN_SECONDS", "30")
    s = Settings(_env_file=None)
    assert s.APP_ENV == "prod"
    assert s.CONSTRUCTION_DETECTION_CONFIDENCE == pytest.approx(0.7)
    assert s.ALERT_COOLDOWN_SECONDS == 30


def test_parse_class_thresholds():
    parsed = Settings.parse_class_thresholds_str("2:0.70, 5:0.65, invalid, 9:bad")
    assert parsed == {2: 0.70, 5: 0.65}
    assert Settings.parse_class_thresholds_str("") == {}


def test_database_url_default():
    s = Settings(_env_file=None)
    assert "sqlite" in s.DATABASE_URL
