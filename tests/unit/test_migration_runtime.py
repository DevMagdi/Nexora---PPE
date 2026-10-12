from __future__ import annotations

import logging

import sqlalchemy as sa

from app.core.config import settings
from app.db.migration_runtime import migration_connect_args, set_migration_lock_timeout


def test_migration_connect_timeout_uses_dbapi_specific_parameter():
    assert migration_connect_args("mssql+pyodbc://user:pass@db/app", 7) == {"timeout": 7}
    assert migration_connect_args("postgresql+psycopg2://user:pass@db/app", 7) == {
        "connect_timeout": 7
    }
    assert migration_connect_args("sqlite:///./test.db", 7) == {"timeout": 7}
    assert migration_connect_args("unknown://host/db", 7) == {}


def test_migration_sets_sql_server_lock_timeout_only_for_sql_server():
    class FakeConnection:
        def __init__(self):
            self.statements: list[str] = []

        def exec_driver_sql(self, statement: str) -> None:
            self.statements.append(statement)

        def commit(self) -> None:
            self.statements.append("<commit>")

    connection = FakeConnection()
    set_migration_lock_timeout(connection, "mssql+pyodbc://user:pass@db/app", 2500)
    assert connection.statements == ["SET LOCK_TIMEOUT 2500", "<commit>"]

    set_migration_lock_timeout(connection, "sqlite:///./test.db", 2500)
    assert connection.statements == ["SET LOCK_TIMEOUT 2500", "<commit>"]


def test_migration_lock_timeout_is_never_interpolated_as_sql():
    class FakeConnection:
        def exec_driver_sql(self, statement: str) -> None:
            raise AssertionError("invalid timeout must be rejected before executing SQL")

    try:
        set_migration_lock_timeout(
            FakeConnection(),
            "mssql+pyodbc://user:pass@db/app",
            "1; DROP TABLE users",  # type: ignore[arg-type]
        )
    except (TypeError, ValueError):
        pass
    else:  # pragma: no cover - assertion branch
        raise AssertionError("non-numeric lock timeout was accepted")


async def test_alembic_upgrade_applies_the_full_schema_to_sqlite(tmp_path, monkeypatch):
    from app.main import upgrade_database

    app_logger = logging.getLogger("app.main")
    root_logger = logging.getLogger()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    database_path = tmp_path / "migration-test.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{database_path.as_posix()}")

    try:
        await upgrade_database()
        assert app_logger.disabled is False
        assert app_logger.isEnabledFor(logging.INFO)
        assert root_logger.level == logging.INFO
    finally:
        root_logger.setLevel(previous_root_level)

    engine = sa.create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        inspector = sa.inspect(engine)
        assert {"users", "cameras", "violations", "alert_log", "audit_logs"}.issubset(
            set(inspector.get_table_names())
        )
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        assert {"role", "is_active", "must_change_password", "token_version"}.issubset(user_columns)
        with engine.connect() as connection:
            revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "20261012sec"
    finally:
        engine.dispose()
