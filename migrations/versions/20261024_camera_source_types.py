"""Typed industrial video sources and explicit safe connection errors.

Revision ID: 20261024src
Revises: 20261024ind

Forward upgrade is additive. Preserve existing camera URIs, rules and sites.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261024src"
down_revision = "20261024ind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cameras") as batch:
        batch.add_column(sa.Column("device_index", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("auth_mode", sa.String(16), nullable=False, server_default="basic")
        )
        batch.add_column(sa.Column("onvif_device_uri", sa.String(500), nullable=True))
        batch.add_column(sa.Column("last_error", sa.String(255), nullable=True))
    cameras = sa.table(
        "cameras", sa.column("source_type", sa.String()), sa.column("source_uri", sa.String())
    )
    # The former RTSP kind accepted both schemes. Keep existing secure streams working.
    op.get_bind().execute(
        cameras.update()
        .where(
            (cameras.c.source_type == "rtsp")
            & (sa.func.lower(cameras.c.source_uri).like("rtsps://%"))
        )
        .values(source_type="rtsps")
    )


def downgrade() -> None:
    raise RuntimeError(
        "Restore a tested backup with the matching application; older versions cannot run these source types"
    )
