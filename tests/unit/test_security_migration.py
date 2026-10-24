from __future__ import annotations

import json
import sqlite3

from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.main import _upgrade_database_sync


def test_migration_upgrades_unversioned_installation_and_removes_obsolete_scope(
    tmp_path, monkeypatch
):
    path = tmp_path / "legacy.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    command.upgrade(Config("alembic.ini"), "bec6d3a1cd21")
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO users (username,password_hash,sector,created_at) VALUES ('site-admin','hash','both','2026-01-01')"
        )
        db.execute(
            "INSERT INTO users (username,password_hash,sector,created_at) VALUES ('retired-account','hash','obsolete','2026-01-01')"
        )
        db.execute(
            "INSERT INTO cameras (name,source_type,source_uri,profile,enabled_classes,is_active,created_at) VALUES ('Gate','rtsp','rtsp://192.168.10.20/live','construction',?,1,'2026-01-01')",
            (json.dumps(["helmet", "unknown"]),),
        )
        db.execute(
            "INSERT INTO cameras (name,source_type,source_uri,profile,enabled_classes,is_active,created_at) VALUES ('Retired','file','old','obsolete','[]',1,'2026-01-01')"
        )
        for camera_id, name in [(1, "NO-Hardhat"), (1, "Unsupported"), (2, "Unsupported")]:
            db.execute(
                "INSERT INTO violations(camera_id,violation_type,confidence,timestamp) VALUES (?,?,.9,'2026-01-01')",
                (camera_id, name),
            )
        db.execute(
            "INSERT INTO alert_log(violation_id,handler_type,sent_at,success) VALUES (3,'db','2026-01-01',1)"
        )
        db.execute("DROP TABLE alembic_version")
    _upgrade_database_sync()
    # The upgrade is repeatable without resetting users/roles or data.
    _upgrade_database_sync()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20261024ind"
        assert db.execute(
            "SELECT username,role,is_active,must_change_password,token_version FROM users ORDER BY id"
        ).fetchall() == [
            ("site-admin", "admin", 1, 1, 1),
            ("retired-account", "viewer", 0, 1, 1),
        ]
        assert db.execute("SELECT name,enabled_classes,is_active FROM cameras").fetchall() == [
            ("Gate", '["helmet"]', 0)
        ]
        assert db.execute("SELECT violation_type FROM violations").fetchall() == [("NO-Hardhat",)]
        assert db.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0] == 0
        assert "profile" not in {row[1] for row in db.execute("PRAGMA table_info(cameras)")}
        assert "sector" not in {row[1] for row in db.execute("PRAGMA table_info(users)")}
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT name FROM sqlite_master WHERE name='sites'").fetchone()


def test_existing_operator_becomes_supervisor_without_losing_admin(tmp_path, monkeypatch):
    path = tmp_path / "security.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    command.upgrade(Config("alembic.ini"), "20261012sec")
    with sqlite3.connect(path) as db:
        for name, role in [("admin", "admin"), ("shift-lead", "operator")]:
            db.execute(
                "INSERT INTO users(username,password_hash,sector,role,created_at) VALUES (?,'hash','construction',?,'2026-01-01')",
                (name, role),
            )
    _upgrade_database_sync()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT role FROM users ORDER BY id").fetchall() == [
            ("admin",),
            ("supervisor",),
        ]
