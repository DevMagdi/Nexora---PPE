from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AuditLog


def hash_identifier(value: str) -> str:
    """One-way, keyed identifier suitable for audit metadata without storing raw IPs."""
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        value.encode("utf-8", errors="replace"),
        hashlib.sha256,
    ).hexdigest()


def add_audit_event(
    db: AsyncSession,
    action: str,
    *,
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    ip_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    safe_details = details or {}
    # A strict JSON round-trip prevents accidental non-serializable data and
    # rejects custom encoder hooks from user-controlled values.
    normalized_details = json.loads(json.dumps(safe_details, ensure_ascii=False, default=str))
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action[:100],
            target_type=target_type[:50] if target_type else None,
            target_id=str(target_id)[:100] if target_id is not None else None,
            ip_hash=ip_hash,
            details=normalized_details,
        )
    )
