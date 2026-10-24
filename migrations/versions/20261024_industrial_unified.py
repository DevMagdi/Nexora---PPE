"""Constrain the installation to industrial safety and add factory/site settings.

Revision ID: 20261024ind
Revises: 20261012sec

Take an encrypted backup before upgrading. Unsupported camera/event data is
removed; unsupported accounts are disabled. All existing sessions are revoked.
This scope reduction is intentionally not reversible by a schema downgrade.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "20261024ind"
down_revision = "20261012sec"
branch_labels = None
depends_on = None

_ALLOWED_KEYS = {"helmet", "vest", "gloves", "boots", "goggles"}
_NEGATIVES = {
    "no hardhat": "NO-Hardhat",
    "no helmet": "NO-Hardhat",
    "no safety vest": "NO-Safety Vest",
    "no vest": "NO-Safety Vest",
    "no gloves": "NO-Gloves",
    "no hand gloves": "NO-Gloves",
    "no safety boots": "NO-Boot",
    "no boots": "NO-Boot",
    "no boot": "NO-Boot",
    "no goggles": "NO-Goggles",
    "no goggle": "NO-Goggles",
}


def upgrade() -> None:
    bind = op.get_bind()
    meta = sa.MetaData()
    users = sa.Table("users", meta, autoload_with=bind)
    cameras = sa.Table("cameras", meta, autoload_with=bind)
    violations = sa.Table("violations", meta, autoload_with=bind)
    alerts = sa.Table("alert_log", meta, autoload_with=bind)
    audit = sa.Table("audit_logs", meta, autoload_with=bind)

    for camera in bind.execute(sa.select(cameras)).mappings().all():
        supported = camera["profile"] in {"construction", "industrial"} and camera[
            "source_type"
        ] in {"rtsp", "file"}
        if not supported:
            event_ids = sa.select(violations.c.id).where(violations.c.camera_id == camera["id"])
            bind.execute(alerts.delete().where(alerts.c.violation_id.in_(event_ids)))
            bind.execute(violations.delete().where(violations.c.camera_id == camera["id"]))
            bind.execute(cameras.delete().where(cameras.c.id == camera["id"]))
            continue
        enabled = camera["enabled_classes"]
        if isinstance(enabled, str):
            try:
                enabled = json.loads(enabled)
            except ValueError:
                enabled = []
        enabled = [key for key in (enabled or []) if key in _ALLOWED_KEYS]
        bind.execute(
            cameras.update()
            .where(cameras.c.id == camera["id"])
            .values(
                enabled_classes=enabled or ["helmet", "vest"],
                is_active=False,
            )
        )

    for event in bind.execute(sa.select(violations)).mappings().all():
        key = " ".join(event["violation_type"].lower().replace("-", " ").replace("_", " ").split())
        normalized = _NEGATIVES.get(key)
        if normalized:
            bind.execute(
                violations.update()
                .where(violations.c.id == event["id"])
                .values(violation_type=normalized)
            )
        else:
            bind.execute(alerts.delete().where(alerts.c.violation_id == event["id"]))
            bind.execute(violations.delete().where(violations.c.id == event["id"]))

    for user in bind.execute(sa.select(users)).mappings().all():
        supported = user["sector"] in {"construction", "industrial", "both"}
        role = "supervisor" if user["role"] == "operator" else user["role"]
        role = role if supported and role in {"admin", "supervisor", "viewer"} else "viewer"
        bind.execute(
            users.update()
            .where(users.c.id == user["id"])
            .values(
                role=role,
                is_active=bool(user["is_active"] and supported),
                token_version=user["token_version"] + 1,
                must_change_password=True,
            )
        )
    # Preserve who/what/when in the audit trail, discard obsolete scope metadata.
    bind.execute(audit.update().values(details={}))

    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("location", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_sites_name"),
    )
    with op.batch_alter_table("cameras") as batch:
        batch.add_column(sa.Column("site_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_cameras_site", "sites", ["site_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_index("ix_cameras_site_id", ["site_id"])
        batch.drop_column("profile", mssql_drop_default=True)
    with op.batch_alter_table("users") as batch:
        batch.drop_column("sector", mssql_drop_default=True)


def downgrade() -> None:
    raise RuntimeError(
        "Scope reduction is irreversible; restore the pre-upgrade encrypted backup instead"
    )
