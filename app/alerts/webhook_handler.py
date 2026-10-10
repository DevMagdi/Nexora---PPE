from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.alerts.base import AlertHandler
from app.core.config import settings
from app.core.logging import get_logger
from app.core.violation_checker import ViolationEvent

logger = get_logger(__name__)


class WebhookHandler(AlertHandler):
    handler_type = "webhook"

    def __init__(self, url: str, timeout: float = settings.WEBHOOK_TIMEOUT_SECONDS) -> None:
        self.url = url
        self.timeout = timeout

    async def send(self, violation: ViolationEvent) -> bool:
        payload = {
            "camera_id": violation.camera_id,
            "violation_type": violation.violation_type,
            "confidence": round(violation.confidence, 4),
            # ✅ timezone-aware UTC بدل utcnow() المهجور (deprecated) في
            # نسخ بايثون الحديثة، ونفس القيمة الفعلية بالظبط.
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frame_path": violation.frame_path,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.url, json=payload)
                resp.raise_for_status()
            logger.info("Webhook alert sent to %s", self.url)
            return True
        except Exception as exc:
            logger.error("Webhook alert failed: %s", exc)
            return False