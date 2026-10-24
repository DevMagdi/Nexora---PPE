from __future__ import annotations

from datetime import UTC, datetime

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
            "timestamp": datetime.now(UTC).isoformat(),
            "frame_path": violation.frame_path,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.url, json=payload)
                resp.raise_for_status()
            logger.info("Webhook alert sent")
            return True
        except Exception as exc:
            # Exception strings may embed secret webhook URLs or signed query values.
            logger.error("Webhook alert failed (%s)", type(exc).__name__)
            return False


class SlackWebhookHandler(AlertHandler):
    handler_type = "slack"

    def __init__(self, url: str, timeout: float = settings.WEBHOOK_TIMEOUT_SECONDS) -> None:
        self.url = url
        self.timeout = timeout

    async def send(self, violation: ViolationEvent) -> bool:
        payload = {
            "text": (
                f":rotating_light: *Mantik PPE Violation Alert*\n"
                f"• *Camera:* #{violation.camera_id}\n"
                f"• *Type:* `{violation.violation_type}`\n"
                f"• *Confidence:* `{violation.confidence:.0%}`"
            )
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.url, json=payload)
                resp.raise_for_status()
            logger.info("Slack alert sent for camera %d", violation.camera_id)
            return True
        except Exception as exc:
            logger.error("Slack webhook alert failed (%s)", type(exc).__name__)
            return False
