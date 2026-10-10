from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger
from app.core.violation_checker import ViolationEvent

logger = get_logger(__name__)


async def save_violation(violation: ViolationEvent) -> Optional[int]:
    """
    يحفظ المخالفة في قاعدة البيانات ويرجع الـ id بتاعها، أو None لو فشل.

    ✅ ده الخطوة الأولى اللي بتحصل *قبل* إرسال أي تنبيه (إيميل/ويبهوك)،
    عشان نقدر نربط كل محاولة إرسال بـ violation_id حقيقي في جدول alert_log
    (قبل كده كان DatabaseHandler بيتسابق مع باقي الـ handlers في
    asyncio.gather، فمفيش ضمان إن الـ violation كانت اتسجلت في الداتابيز
    قبل ما باقي الـ handlers تحاول تربط نفسها بيها).
    """
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

            logger.info(
                "Violation saved to DB: id=%s camera=%d type=%s",
                db_violation.id,
                violation.camera_id,
                violation.violation_type,
            )
            return db_violation.id
    except Exception as exc:
        logger.error("Failed to save violation to DB: %s", exc)
        return None


async def record_alert_log(
    violation_id: Optional[int],
    handler_type: str,
    success: bool,
    error_msg: Optional[str] = None,
) -> None:
    """
    يسجّل محاولة إرسال تنبيه (ناجحة أو فاشلة) في جدول alert_log.

    ⚠️ أي خطأ هنا بيتسجل في اللوج بس *مش* بيتعمله raise — لأن فشل تسجيل
    اللوج مينفعش يوقف أو يأثر على نتيجة إرسال التنبيه نفسه.
    """
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