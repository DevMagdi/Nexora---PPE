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
