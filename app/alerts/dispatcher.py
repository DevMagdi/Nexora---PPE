from __future__ import annotations

import asyncio

from app.alerts.base import AlertHandler
from app.core.logging import get_logger
from app.core.violation_checker import ViolationEvent
from app.db.repository import record_alert_log

logger = get_logger(__name__)


class AlertDispatcher:
    """
    بيوزّع الـ ViolationEvent على كل الـ handlers المفعّلة بالتوازي،
    وبيسجّل نتيجة كل محاولة (نجاح/فشل + رسالة الخطأ لو فيه) في جدول
    alert_log تلقائيًا — عشان تقدر بعدين ترجع تشوف ليه إيميل معين
    فشل بالظبط من غير ما تفتش في ملفات اللوج.
    """

    def __init__(self, handlers: list[AlertHandler]) -> None:
        self.handlers = handlers

    async def dispatch(self, violation: ViolationEvent) -> None:
        if not self.handlers:
            return

        results = await asyncio.gather(
            *[self._run(h, violation) for h in self.handlers],
            return_exceptions=True,
        )
        for handler, result in zip(self.handlers, results):
            if isinstance(result, Exception):
                logger.error("Handler %s raised: %s", handler.handler_type, result)

    async def _run(self, handler: AlertHandler, violation: ViolationEvent) -> bool:
        error_msg: str | None = None
        try:
            success = await handler.send(violation)
            if not success:
                error_msg = "Handler reported failure (see handler logs for details)"
                logger.warning("Handler %s reported failure", handler.handler_type)
        except Exception as exc:
            success = False
            error_msg = str(exc)
            logger.exception("Handler %s exception: %s", handler.handler_type, exc)

        await record_alert_log(
            violation_id=violation.violation_id,
            handler_type=handler.handler_type,
            success=success,
            error_msg=error_msg,
        )
        return success