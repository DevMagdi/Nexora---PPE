from __future__ import annotations

import os

import aiosmtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.alerts.base import AlertHandler
from app.core.config import settings
from app.core.logging import get_logger
from app.core.violation_checker import ViolationEvent

logger = get_logger(__name__)


class EmailHandler(AlertHandler):
    handler_type = "email"

    def _resolve_frame_path(self, frame_path: str) -> str:
        """
        violation.frame_path عندنا غالبًا بيكون relative مثل:
          camera_1/violation_123.jpg

        هنا بنحوّله لمسار كامل داخل FRAMES_DIR.
        ولو هو أصلًا absolute بنسيبه زي ما هو.
        """
        if not frame_path:
            return ""

        frame_path = frame_path.replace("\\", "/").lstrip("/")

        if os.path.isabs(frame_path):
            return frame_path

        return os.path.join(settings.FRAMES_DIR, frame_path)

    async def send(self, violation: ViolationEvent) -> bool:
        if not settings.SENDER_EMAIL or not settings.RECEIVER_EMAIL or not settings.EMAIL_PASSWORD:
            logger.warning("Email not configured (sender/receiver/password missing), skipping alert")
            return False

        message = MIMEMultipart()
        message["From"] = settings.SENDER_EMAIL
        message["To"] = settings.RECEIVER_EMAIL
        message["Subject"] = f"Alert: {violation.violation_type} on Camera {violation.camera_id}"

        body = (
            f"A safety violation was detected on Camera {violation.camera_id}.\n"
            f"Violation type: {violation.violation_type}\n"
            f"Confidence: {violation.confidence:.0%}\n"
            "Please review the attached frame if available."
        )
        message.attach(MIMEText(body, "plain"))

        if violation.frame_path:
            full_path = self._resolve_frame_path(violation.frame_path)
            if full_path and os.path.exists(full_path):
                try:
                    with open(full_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={os.path.basename(full_path)}",
                    )
                    message.attach(part)
                except Exception as exc:
                    logger.warning("Could not attach frame (%s): %s", full_path, exc)
            else:
                logger.warning("Frame path does not exist, sending email without attachment: %s", full_path)

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SENDER_EMAIL,
                password=settings.EMAIL_PASSWORD,
                start_tls=True,
                timeout=settings.ALERT_SMTP_TIMEOUT_SECONDS,
            )
            logger.info(
                "Email alert sent for camera %d (%s)",
                violation.camera_id,
                violation.violation_type,
            )
            return True
        except Exception as exc:
            logger.error("Failed to send email alert: %s", exc)
            return False