from __future__ import annotations

import sqlite3

from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.main import _upgrade_database_sync

ROOT_CONFIG = "alembic.ini"


def _config(database_url: str) -> Config:
    config = Config(ROOT_CONFIG)
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def test_security_migration_upgrades_existing_installation(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path}"
    config = _config(database_url)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")

    # Create the schema exactly as the old install did, then remove Alembic's
    # version marker to model a deployed create_all() database.
    command.upgrade(config, "bec6d3a1cd21")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO users (username, password_hash, sector, created_at) "
            "VALUES ('legacy-admin', 'old-hash', 'both', '2026-01-01 00:00:00')"
        )
        connection.execute(
            "INSERT INTO users (username, password_hash, sector, created_at) "
            "VALUES ('legacy-user', 'old-hash', 'medical', '2026-01-01 00:00:00')"
        )
        connection.execute("DROP TABLE alembic_version")

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    _upgrade_database_sync()

    with sqlite3.connect(database_path) as connection:
        users = connection.execute(
            "SELECT username, role, is_active, must_change_password, token_version "
            "FROM users ORDER BY id"
        ).fetchall()
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert users == [
        ("legacy-admin", "admin", 1, 1, 0),
        ("legacy-user", "operator", 1, 1, 0),
    ]
    assert "audit_logs" in tables
    assert revision == "20261012sec"
