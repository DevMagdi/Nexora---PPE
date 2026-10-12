from __future__ import annotations

import re

# Matches the password part of ``scheme://user:password@host/...`` URLs. The
# password may itself contain ``@`` (unencoded), so match greedily up to the
# last ``@`` before the host, without crossing a ``/``.
_CREDENTIALS_RE = re.compile(r"(://[^/\s@]+:)[^/\s]*(@)")

_BACKEND_LABELS = {
    "sqlite": "SQLite",
    "sqlite+aiosqlite": "SQLite (aiosqlite)",
    "postgresql": "PostgreSQL",
    "postgresql+asyncpg": "PostgreSQL (asyncpg)",
    "postgresql+psycopg2": "PostgreSQL (psycopg2)",
    "mssql": "SQL Server",
    "mssql+aioodbc": "SQL Server (aioodbc)",
    "mssql+pyodbc": "SQL Server (pyodbc)",
}


def redact_database_url(url: str) -> str:
    """Hide the password in a database URL so it is safe to log."""
    return _CREDENTIALS_RE.sub(r"\1***\2", url or "")


def database_backend_label(database_url: str) -> str:
    """Short backend name for startup logs (no credentials involved)."""
    scheme = (database_url or "").split(":", 1)[0].strip().lower()
    return _BACKEND_LABELS.get(scheme, scheme or "unknown")


def _missing_module(text: str, module: str) -> bool:
    return f"no module named '{module}'" in text or f'no module named "{module}"' in text


def database_startup_hint(database_url: str, exc: BaseException) -> str:
    """Build an actionable, credential-safe error message for DB startup failures."""
    redacted = redact_database_url(database_url)
    scheme = (database_url or "").split(":", 1)[0].strip().lower()
    lowered = f"{type(exc).__name__}: {exc}".lower()

    lines = [f"Database startup failed for {redacted} ({type(exc).__name__}: {exc})".rstrip()]

    if scheme.startswith("mssql"):
        lines.append("SQL Server backend detected (mssql). Local checklist:")
        lines.append("  1. Install the SQL Server drivers: pip install -r requirements/mssql.txt")
        lines.append(
            "  2. Install 'ODBC Driver 18 for SQL Server' from Microsoft and make "
            "sure the server is reachable from this machine."
        )
        lines.append(
            "  3. Use a URL like: "
            "mssql+aioodbc://USER:PASSWORD@HOST:1433/DBNAME?driver=ODBC+Driver+18+for+SQL+Server"
        )
        if "driver" in lowered and (
            "not found" in lowered or "can't open lib" in lowered or "data source name" in lowered
        ):
            lines.append(
                "  The error mentions the ODBC driver itself — step 2 above is the likely fix."
            )
        if _missing_module(lowered, "aioodbc") or _missing_module(lowered, "pyodbc"):
            lines.append("  A SQL Server DBAPI module is missing — step 1 above is the fix.")
    elif scheme.startswith("postgresql"):
        if _missing_module(lowered, "asyncpg"):
            lines.append("Missing asyncpg (runtime driver) — install it with: pip install asyncpg")
        if _missing_module(lowered, "psycopg2"):
            lines.append(
                "Missing psycopg2 (needed by Alembic migrations) — install it with: "
                "pip install psycopg2-binary"
            )
        if not any("pip install" in line for line in lines[1:]):
            lines.append(
                "Check that PostgreSQL is running and DATABASE_URL credentials/host are correct."
            )
    elif scheme.startswith("sqlite"):
        if _missing_module(lowered, "aiosqlite"):
            lines.append("Missing aiosqlite — install it with: pip install aiosqlite")
    else:
        lines.append(
            f"Unsupported DATABASE_URL scheme {scheme!r}. Use sqlite+aiosqlite (dev default), "
            "postgresql+asyncpg, or mssql+aioodbc."
        )
    lines.append("See docs/LOCAL_RUN_TROUBLESHOOTING_AR.md for the full local-run checklist.")
    return "\n".join(lines)
