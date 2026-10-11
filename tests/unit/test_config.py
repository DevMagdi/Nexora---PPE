from __future__ import annotations

import pytest

from app.core.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.APP_ENV == "dev"
    assert s.CONSTRUCTION_MODEL_PATH == "Model/ppe.pt"
    assert s.MEDICAL_MODEL_PATH == "Model/bestMedicalModel2.pt"
    assert s.CONSTRUCTION_DETECTION_CONFIDENCE == pytest.approx(0.10)
    assert s.MEDICAL_DETECTION_CONFIDENCE == pytest.approx(0.15)
    assert s.ALERT_COOLDOWN_SECONDS == 60


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
