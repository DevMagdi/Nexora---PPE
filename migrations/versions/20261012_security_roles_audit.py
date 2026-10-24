"""Add roles, password/session controls, and security audit events.

Revision ID: 20261012sec
Revises: bec6d3a1cd21
Create Date: 2026-10-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261012sec"
down_revision: str | Sequence[str] | None = "bec6d3a1cd21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    additions = (
        ("role", sa.String(length=20), "'viewer'"),
        ("is_active", sa.Boolean(), sa.true()),
        ("must_change_password", sa.Boolean(), sa.true()),
        ("token_version", sa.Integer(), "0"),
        ("failed_login_attempts", sa.Integer(), "0"),
        ("last_failed_login_at", sa.DateTime(), None),
        ("locked_until", sa.DateTime(), None),
    )
    for name, column_type, default in additions:
        if name not in user_columns:
            options = {"nullable": default is None}
            if default is not None:
                options["nullable"] = False
                options["server_default"] = (
                    default if not isinstance(default, str) else sa.text(default)
                )
            op.add_column("users", sa.Column(name, column_type, **options))

    # The old app had no roles. Preserve its all-operator capabilities for the
    # earliest existing account as the installation admin and make every old
    # account rotate its password after the security upgrade.
    op.execute(sa.text("UPDATE users SET role = 'operator'"))
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE id = (SELECT MIN(id) FROM users)"))
    users_table = sa.table(
        "users",
        sa.column("must_change_password", sa.Boolean()),
    )
    op.execute(sa.update(users_table).values(must_change_password=sa.true()))

    tables = set(inspector.get_table_names())
    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "actor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("target_type", sa.String(length=50), nullable=True),
            sa.Column("target_id", sa.String(length=100), nullable=True),
            sa.Column("ip_hash", sa.String(length=64), nullable=True),
            sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_audit_logs_id", "audit_logs", ["id"], unique=False)
        op.create_index(
            "ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False
        )
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "audit_logs" in inspector.get_table_names():
        op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
        op.drop_index("ix_audit_logs_action", table_name="audit_logs")
        op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
        op.drop_index("ix_audit_logs_id", table_name="audit_logs")
        op.drop_table("audit_logs")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    for name in (
        "locked_until",
        "last_failed_login_at",
        "failed_login_attempts",
        "token_version",
        "must_change_password",
        "is_active",
        "role",
    ):
        if name in user_columns:
            op.drop_column("users", name)
