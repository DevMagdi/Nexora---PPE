from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# ✅ بنضيف جذر المشروع لـ sys.path يدويًا، عشان نقدر نعمل
# import لحزمة app من جوه env.py، بغض النظر عن المسار اللي
# alembic بيتنفذ منه فعليًا.
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402
from app.db.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ بنربط target_metadata بالموديلز الحقيقية بتاعة التطبيق،
# عشان --autogenerate يقدر يقارن الموديلز بالداتابيز الفعلية.
target_metadata = Base.metadata


def get_sync_database_url() -> str:
    """
    Alembic بيشتغل sync افتراضيًا، لكن DATABASE_URL بتاعنا مبني على
    aioodbc (async) عشان التطبيق نفسه. هنا بنحوّل الـ URL لنسخة sync
    (pyodbc) خصيصًا لعمليات الـ migration بس، من غير ما نلمس أي حاجة
    في إعدادات التطبيق الأساسية.
    """
    return settings.DATABASE_URL.replace("mssql+aioodbc", "mssql+pyodbc")


# ✅ بنحط الـ URL الصحيح (من .env الحقيقي بتاعنا) بدل الـ placeholder
# الموجود في alembic.ini.
config.set_main_option("sqlalchemy.url", get_sync_database_url())


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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()