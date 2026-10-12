from __future__ import annotations

from sqlalchemy import select

from app.core.auth import hash_password
from app.core.logging import get_logger
from app.core.violation_checker import ViolationEvent

logger = get_logger(__name__)


async def save_violation(violation: ViolationEvent) -> int | None:
    try:
        from app.db.models import Violation
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            db_violation = Violation(
                camera_id=violation.camera_id,
                violation_type=violation.violation_type,
                confidence=violation.confidence,
                frame_path=violation.frame_path,
            )
            session.add(db_violation)
            await session.commit()
            await session.refresh(db_violation)
            return db_violation.id
    except Exception as exc:
        logger.error("Failed to save violation to DB: %s", exc)
        return None


async def record_alert_log(
    violation_id: int | None,
    handler_type: str,
    success: bool,
    error_msg: str | None = None,
) -> None:
    try:
        from app.db.models import AlertLog
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            log = AlertLog(
                violation_id=violation_id,
                handler_type=handler_type,
                success=success,
                error_msg=(error_msg[:1000] if error_msg else None),
            )
            session.add(log)
            await session.commit()
    except Exception as exc:
        logger.error("Failed to record alert log (%s): %s", handler_type, exc)


async def get_user_by_username(username: str):
    from app.db.models import User
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        q = select(User).where(User.username == username)
        res = await session.execute(q)
        return res.scalar_one_or_none()


async def ensure_bootstrap_user(username: str, password: str, sector: str) -> None:
    """ينشئ user واحد عند أول تشغيل لو جدول users فاضي."""
    from app.db.models import User
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).limit(1))
        any_user = res.scalar_one_or_none()
        if any_user:
            return

        u = User(
            username=username,
            password_hash=hash_password(password),
            sector=sector,
            role="admin",
            is_active=True,
            must_change_password=True,
        )
        session.add(u)
        await session.commit()
        logger.warning(
            "Bootstrap user created: username=%s sector=%s (CHANGE PASSWORD!)",
            username,
            sector,
        )
