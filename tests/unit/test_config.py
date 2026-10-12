from __future__ import annotations

import pytest

from app.core.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.APP_ENV == "dev"
    assert s.CONSTRUCTION_MODEL_PATH == "Model/ppe.pt"
    assert s.MEDICAL_MODEL_PATH == "Model/bestMedicalModel.pt"
    # الافتراضيات اترفعت لحارس الدقة (precision floor) — كانت 0.10/0.15
    assert s.CONSTRUCTION_DETECTION_CONFIDENCE == pytest.approx(0.25)
    assert s.MEDICAL_DETECTION_CONFIDENCE == pytest.approx(0.25)
    assert s.DETECTION_CONFIDENCE_FLOOR == pytest.approx(0.25)
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


def test_precision_guard_defaults():
    """حراس الدقة الجدد (من إصلاح لوج 2026-10-12) لازم يكون ليهم حدود منطقية."""
    s = Settings(_env_file=None)
    # سقف الكشوف الصناعية أقل من 0.9 (الهوريستيك مش موديل)
    assert 0.4 <= s.SKIN_SYNTHETIC_MIN_CONF < s.SKIN_SYNTHETIC_MAX_CONF <= 0.9
    # دليل الجلد لمخالفة لازم يكون أقوى من أرضية العرض
    assert s.SKIN_NEGATIVE_MIN_CONF >= s.SKIN_SYNTHETIC_MIN_CONF
    # الفحص التشريحي على Person موثوق بس
    assert 0.2 <= s.SKIN_MIN_PERSON_CONF <= 0.6
    # إسقاط الموجب صارم: الهوريستيك لازم يكون أقوى من سقف الموجب المسموح إسقاطه
    assert s.SKIN_POSITIVE_OVERRIDE_MIN_CONF > s.SKIN_POSITIVE_OVERRIDE_MAX_CONF
    # لوج SQL مقفول افتراضيًا (كان بيطبع كل استعلام مرتين في dev)
    assert s.DB_SQL_ECHO is False


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
