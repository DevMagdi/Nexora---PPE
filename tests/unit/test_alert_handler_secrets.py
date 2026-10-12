from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.alerts import webhook_handler


class FailingClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json):
        raise httpx.ConnectError(f"failed to connect to {url}")


@pytest.mark.asyncio
async def test_webhook_logs_and_alert_records_do_not_leak_secret_url(monkeypatch):
    secret = "https://hooks.customer.lan/hook/super-secret-token"
    monkeypatch.setattr(webhook_handler.httpx, "AsyncClient", lambda timeout: FailingClient())
    monkeypatch.setattr(webhook_handler.logger, "error", Mock())
    handler = webhook_handler.WebhookHandler(secret)
    violation = SimpleNamespace(
        camera_id=7,
        violation_type="NO-Hardhat",
        confidence=0.8,
        frame_path=None,
    )

    assert await handler.send(violation) is False
    assert secret not in str(webhook_handler.logger.error.call_args)
