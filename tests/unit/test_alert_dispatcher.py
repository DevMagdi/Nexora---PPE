from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.alerts.base import AlertHandler
from app.alerts.dispatcher import AlertDispatcher
from app.core.violation_checker import ViolationEvent


def make_violation(camera_id: int = 1) -> ViolationEvent:
    return ViolationEvent(
        camera_id=camera_id,
        violation_type="NO-Hardhat",
        confidence=0.85,
        violation_id=42,
    )


class SuccessHandler(AlertHandler):
    handler_type = "success"

    def __init__(self):
        self.called = False

    async def send(self, violation: ViolationEvent) -> bool:
        self.called = True
        return True


class FailHandler(AlertHandler):
    handler_type = "fail"

    def __init__(self):
        self.called = False

    async def send(self, violation: ViolationEvent) -> bool:
        self.called = True
        return False


class ErrorHandler(AlertHandler):
    handler_type = "error"

    def __init__(self):
        self.called = False

    async def send(self, violation: ViolationEvent) -> bool:
        self.called = True
        raise RuntimeError("simulated error")


async def test_dispatcher_calls_all_handlers():
    h1, h2 = SuccessHandler(), SuccessHandler()
    dispatcher = AlertDispatcher([h1, h2])
    with patch("app.alerts.dispatcher.record_alert_log", new=AsyncMock()) as mock_log:
        await dispatcher.dispatch(make_violation())
    assert h1.called
    assert h2.called
    assert mock_log.await_count == 2


async def test_failing_handler_does_not_block_others():
    fail = FailHandler()
    success = SuccessHandler()
    dispatcher = AlertDispatcher([fail, success])
    with patch("app.alerts.dispatcher.record_alert_log", new=AsyncMock()):
        await dispatcher.dispatch(make_violation())
    assert fail.called
    assert success.called


async def test_error_handler_does_not_block_others():
    err = ErrorHandler()
    success = SuccessHandler()
    dispatcher = AlertDispatcher([err, success])
    with patch("app.alerts.dispatcher.record_alert_log", new=AsyncMock()):
        await dispatcher.dispatch(make_violation())
    assert err.called
    assert success.called


async def test_empty_dispatcher():
    dispatcher = AlertDispatcher([])
    await dispatcher.dispatch(make_violation())
