from __future__ import annotations

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

# Alembic imports SQLAlchemy, so the native-extension guard has to run first: on
# machines where an Application Control policy blocks SQLAlchemy's compiled
# modules it swaps in the pure-Python twins (see app/native_compat.py).
from app.native_compat import ensure_sqlalchemy_importable  # noqa: E402

ensure_sqlalchemy_importable()

from alembic import context  # noqa: E402
from sqlalchemy import engine_from_config, pool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.migration_runtime import migration_connect_args, set_migration_lock_timeout  # noqa: E402
from app.db.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    # Preserve Nexora's own configured loggers and the server's active log level;
    # fileConfig defaults to disabling unlisted loggers and sets root to WARNING,
    # which used to hide every INFO log after Alembic returned.
    root_logger = logging.getLogger()
    root_level = root_logger.level
    fileConfig(config.config_file_name, disable_existing_loggers=False)
    root_logger.setLevel(root_level)

migration_logger = logging.getLogger("alembic.runtime.migration")
target_metadata = Base.metadata


def get_sync_database_url() -> str:
    """Converts async SQLAlchemy URLs into synchronous URLs for Alembic."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite+aiosqlite"):
        return url.replace("sqlite+aiosqlite", "sqlite", 1)
    if url.startswith("postgresql+asyncpg"):
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    if url.startswith("mssql+aioodbc"):
        return url.replace("mssql+aioodbc", "mssql+pyodbc", 1)
    return url


# Alembic configparser treats percent signs as interpolation markers; escape
# credentials containing '%' before setting a database URL from the environment.
config.set_main_option("sqlalchemy.url", get_sync_database_url().replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with visible connection/apply stages."""
    connectable = None
    sync_url = get_sync_database_url()
    try:
        migration_logger.info("Opening database connection for Alembic migrations...")
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            connect_args=migration_connect_args(
                sync_url,
                settings.DB_MIGRATION_CONNECT_TIMEOUT_SECONDS,
            ),
        )

        with connectable.connect() as connection:
            migration_logger.info(
                "Alembic database connection established (dialect=%s)",
                connection.dialect.name,
            )
            set_migration_lock_timeout(
                connection,
                sync_url,
                settings.DB_MIGRATION_LOCK_TIMEOUT_MS,
            )
            if sync_url.lower().startswith("mssql"):
                migration_logger.info(
                    "SQL Server migration lock wait limited to %s ms",
                    settings.DB_MIGRATION_LOCK_TIMEOUT_MS,
                )

            migration_logger.info("Checking current schema revision and applying pending migrations...")
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
            migration_logger.info("Alembic migration run completed")
    except Exception as exc:
        # Direct `alembic upgrade head` runs bypass app.main's wrapper, so hint here too.
        from app.db.driver_hints import database_startup_hint

        raise RuntimeError(database_startup_hint(settings.DATABASE_URL, exc)) from exc
    finally:
        if connectable is not None:
            connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
