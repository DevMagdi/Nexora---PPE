from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.violation_checker import ViolationEvent


class AlertHandler(ABC):
    """
    عقد موحّد لأي قناة تنبيه (Email, Webhook, Slack...). كل handler جديد
    لازم يرث من هنا وينفّذ send() بس — الـ AlertDispatcher هو المسؤول عن
    تسجيل نتيجة الإرسال في alert_log، مش الـ handler نفسه.
    """

    @property
    @abstractmethod
    def handler_type(self) -> str: ...

    @abstractmethod
    async def send(self, violation: ViolationEvent) -> bool:
        """Send alert. Returns True on success, False on failure."""
        ...