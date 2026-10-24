"""baseline schema

Revision ID: bec6d3a1cd21
Revises:
Create Date: 2026-10-10 14:41:54.565368

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bec6d3a1cd21"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema across SQLite, PostgreSQL, and SQL Server."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column(
                "sector", sa.String(length=20), nullable=False, server_default="construction"
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_users_id", "users", ["id"], unique=False)
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    if "cameras" not in existing_tables:
        op.create_table(
            "cameras",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("source_type", sa.String(length=20), nullable=False),
            sa.Column("source_uri", sa.String(length=500), nullable=False),
            sa.Column(
                "profile", sa.String(length=20), nullable=False, server_default="construction"
            ),
            sa.Column("enabled_classes", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_cameras_id", "cameras", ["id"], unique=False)

    if "violations" not in existing_tables:
        op.create_table(
            "violations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "camera_id",
                sa.Integer(),
                sa.ForeignKey("cameras.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("violation_type", sa.String(length=100), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("frame_path", sa.String(length=500), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_violations_id", "violations", ["id"], unique=False)
        op.create_index("ix_violations_camera_id", "violations", ["camera_id"], unique=False)
        op.create_index(
            "ix_violations_violation_type", "violations", ["violation_type"], unique=False
        )
        op.create_index("ix_violations_timestamp", "violations", ["timestamp"], unique=False)

    if "alert_log" not in existing_tables:
        op.create_table(
            "alert_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "violation_id",
                sa.Integer(),
                sa.ForeignKey("violations.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("handler_type", sa.String(length=50), nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=False),
            sa.Column("success", sa.Boolean(), nullable=False),
            sa.Column("error_msg", sa.String(length=1000), nullable=True),
        )
        op.create_index("ix_alert_log_id", "alert_log", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table in ("alert_log", "violations", "cameras", "users"):
        if table in existing_tables:
            op.drop_table(table)
