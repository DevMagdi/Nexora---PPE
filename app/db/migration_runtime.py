from __future__ import annotations

from urllib.parse import urlsplit


def migration_connect_args(database_url: str, timeout_seconds: int) -> dict[str, int]:
    """Return the DBAPI-specific connection timeout for Alembic's sync engine."""
    scheme = urlsplit(database_url).scheme.lower()
    if scheme.startswith("mssql"):
        # pyodbc uses ``timeout`` for the login/connection timeout.
        return {"timeout": timeout_seconds}
    if scheme.startswith("postgresql"):
        # psycopg2 names the same setting ``connect_timeout``.
        return {"connect_timeout": timeout_seconds}
    if scheme.startswith("sqlite"):
        return {"timeout": timeout_seconds}
    return {}


def set_migration_lock_timeout(connection, database_url: str, timeout_ms: int) -> None:
    """Bound SQL Server lock waits so another process cannot stall app startup forever."""
    if urlsplit(database_url).scheme.lower().startswith("mssql"):
        # This is an integer setting, never user-provided SQL; validate it anyway
        # because the helper is also callable directly from tests/tools.
        timeout = int(timeout_ms)
        if timeout < 1:
            raise ValueError("SQL Server migration lock timeout must be positive")
        connection.exec_driver_sql(f"SET LOCK_TIMEOUT {timeout}")
        # `exec_driver_sql` starts SQLAlchemy's autobegin transaction. Commit
        # this session setting before Alembic opens its own migration transaction.
        connection.commit()
