from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_user_facing_identity_is_mantik_while_existing_storage_and_cookies_stay_compatible():
    for name in [
        "frontend/index.html",
        "frontend/src/components/Brand.tsx",
        "frontend/src/auth/AuthGate.tsx",
        "frontend/src/App.tsx",
        "README.md",
        "app/alerts/email_handler.py",
        "app/alerts/webhook_handler.py",
    ]:
        text = (ROOT / name).read_text()
        assert "mantik" in text.lower()
        # Hook module paths are internal compatibility names, not visible copy.
        text = text.replace("@/hooks/useNexora", "")
        assert "nexora" not in text.lower(), name
    manifest = json.loads((ROOT / "frontend/package-lock.json").read_text())
    package = json.loads((ROOT / "frontend/package.json").read_text())
    assert (
        manifest["name"]
        == manifest["packages"][""]["name"]
        == package["name"]
        == "mantik-industrial-console"
    )
    config = (ROOT / "app/core/config.py").read_text()
    assert 'ACCESS_COOKIE_NAME: str = "nexora_access"' in config
    assert 'MEDIA_COOKIE_NAME: str = "nexora_media"' in config
    assert 'MAGIC = b"NEXORA1"' in (ROOT / "app/backup.py").read_text()

    assert 'archive="mantik-postgres-' in (ROOT / "scripts/backup_postgres.sh").read_text()


async def test_email_and_slack_deliver_mantik_identity_without_real_external_services(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.alerts import email_handler, webhook_handler
    from app.core.config import settings
    from app.core.violation_checker import ViolationEvent

    for key, value in {
        "SENDER_EMAIL": "alerts@example.invalid",
        "RECEIVER_EMAIL": "supervisor@example.invalid",
        "EMAIL_PASSWORD": "test-only-not-a-real-password",
    }.items():
        monkeypatch.setattr(settings, key, value)
    send = AsyncMock()
    monkeypatch.setattr(email_handler.aiosmtplib, "send", send)
    event = ViolationEvent(44, "NO-Hardhat", 0.9)
    assert await email_handler.EmailHandler().send(event) is True
    message = send.await_args.args[0]
    assert message["Subject"] == "Mantik PPE Alert: NO-Hardhat on Camera 44"
    assert "nexora" not in message.as_string().lower()
    client = SimpleNamespace(
        post=AsyncMock(return_value=SimpleNamespace(raise_for_status=lambda: None))
    )
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(webhook_handler.httpx, "AsyncClient", lambda **_kwargs: context)
    assert (
        await webhook_handler.SlackWebhookHandler("https://hooks.example.invalid/test").send(event)
        is True
    )
    text = client.post.await_args.kwargs["json"]["text"]
    assert "Mantik PPE Violation Alert" in text
    assert "#44" in text and "NO-Hardhat" in text and "90%" in text
    assert "nexora" not in text.lower()
