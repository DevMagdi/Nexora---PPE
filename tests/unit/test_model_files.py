"""Model weights and DB startup errors must be actionable, not obscure tracebacks."""

from __future__ import annotations

import pytest


def test_require_model_file_returns_existing(tmp_path, monkeypatch):
    detector = pytest.importorskip("app.core.detector")
    monkeypatch.chdir(tmp_path)
    weights = tmp_path / "Model" / "ppe.pt"
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"weights")

    assert (
        detector.require_model_file(
            "Model/ppe.pt",
            fallbacks=("Model/other.pt",),
            setting_name="CONSTRUCTION_MODEL_PATH",
        )
        == "Model/ppe.pt"
    )


def test_require_model_file_lists_candidates_when_missing(tmp_path, monkeypatch):
    detector = pytest.importorskip("app.core.detector")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="CONSTRUCTION_MODEL_PATH") as exc_info:
        detector.require_model_file(
            "Model/missing.pt",
            fallbacks=("Model/other.pt",),
            setting_name="CONSTRUCTION_MODEL_PATH",
        )
    message = str(exc_info.value)
    assert "Model/missing.pt" in message
    assert "Model/other.pt" in message


def test_redact_database_url_hides_password():
    from app.db.driver_hints import redact_database_url

    assert (
        redact_database_url("mssql+aioodbc://sa:P@ssw0rd@dbhost:1433/app")
        == "mssql+aioodbc://sa:***@dbhost:1433/app"
    )
    assert redact_database_url("sqlite+aiosqlite:///./ppe_detection.db") == (
        "sqlite+aiosqlite:///./ppe_detection.db"
    )


def test_database_backend_label():
    from app.db.driver_hints import database_backend_label

    assert "SQL Server" in database_backend_label("mssql+aioodbc://u:p@h/db")
    assert "SQLite" in database_backend_label("sqlite+aiosqlite:///./ppe_detection.db")
    assert "PostgreSQL" in database_backend_label("postgresql+asyncpg://u:p@h/db")


def test_mssql_startup_hint_is_actionable_and_safe():
    from app.db.driver_hints import database_startup_hint

    hint = database_startup_hint(
        "mssql+aioodbc://sa:Sup3rSecret@dbhost:1433/app",
        ModuleNotFoundError("No module named 'aioodbc'"),
    )
    assert "requirements/mssql.txt" in hint
    assert "ODBC Driver" in hint
    assert "Sup3rSecret" not in hint
    assert "LOCAL_RUN_TROUBLESHOOTING" in hint


def test_unknown_scheme_hint_lists_supported_backends():
    from app.db.driver_hints import database_startup_hint

    hint = database_startup_hint("oracle://u:p@h/db", RuntimeError("boom"))
    assert "sqlite+aiosqlite" in hint
    assert "oracle" in hint


def _mock_ultralytics(monkeypatch, side_effect=None):
    import sys
    from unittest.mock import MagicMock

    fake_ultralytics = MagicMock()
    if side_effect is not None:
        fake_ultralytics.YOLO.side_effect = side_effect
    else:
        fake_model = MagicMock()
        fake_model.names = {0: "mask", 1: "no mask"}
        fake_ultralytics.YOLO.return_value = fake_model
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    return fake_ultralytics


def test_empty_weight_file_fails_fast_with_actionable_message(tmp_path, monkeypatch):
    """ملف أوزان فاضي (نسخة/تحميل ناقص) لازم يطلع رسالة واضحة مش Errno غامض."""
    from app.core.detector import PPEDetector

    _mock_ultralytics(monkeypatch)
    model_dir = tmp_path / "Model"
    model_dir.mkdir()
    (model_dir / "empty.pt").write_bytes(b"")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError) as exc_info:
        PPEDetector("Model/empty.pt", 0.25, 0.35, "", setting_name="MEDICAL_MODEL_PATH")

    message = str(exc_info.value)
    assert "Model/empty.pt" in message
    assert "MEDICAL_MODEL_PATH" in message
    assert "empty" in message.lower()


def test_truncated_weight_file_wraps_ultralytics_error(tmp_path, monkeypatch):
    """خطأ ultralytics الغامض (OSError/TypeError) بيتحوّل لرسالة تشغيلية فيها السبب."""
    from app.core.detector import PPEDetector

    _mock_ultralytics(monkeypatch, side_effect=OSError(22, "Invalid argument"))
    model_dir = tmp_path / "Model"
    model_dir.mkdir()
    (model_dir / "truncated.pt").write_bytes(b"PK\x03\x04not-a-real-archive")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError) as exc_info:
        PPEDetector("Model/truncated.pt", 0.25, 0.35, "", setting_name="MEDICAL_MODEL_PATH")

    message = str(exc_info.value)
    assert "Model/truncated.pt" in message
    assert "MEDICAL_MODEL_PATH" in message
    assert "OSError" in message
    assert "Invalid argument" in message
    assert exc_info.value.__cause__ is not None


def test_valid_weights_still_load_through_the_wrapper(tmp_path, monkeypatch):
    from app.core.detector import PPEDetector

    fake_ultralytics = _mock_ultralytics(monkeypatch)
    model_dir = tmp_path / "Model"
    model_dir.mkdir()
    (model_dir / "ok.pt").write_bytes(b"PK\x03\x04real-ish-bytes")
    monkeypatch.chdir(tmp_path)

    detector = PPEDetector("Model/ok.pt", 0.25, 0.35, "")

    fake_ultralytics.YOLO.assert_called_once_with("Model/ok.pt")
    assert detector.class_names == {0: "mask", 1: "no mask"}
