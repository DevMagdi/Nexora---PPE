from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.api.routes import stream
from app.core.auth import create_access_token, media_cookie_name
from app.db.models import Camera, User


class FakeDB:
    def __init__(self, user, camera, events):
        self.user = user
        self.camera = camera
        self.events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, model, item_id):
        self.events.append(f"db:{model.__name__}")
        if model is User:
            return self.user
        if model is Camera:
            return self.camera
        return None


class FakeManager:
    def __init__(self, events, running_values):
        self.events = events
        self.running_values = iter(running_values)
        self.queue = asyncio.Queue()

    def is_running(self, camera_id):
        self.events.append("manager:is_running")
        return next(self.running_values)

    def subscribe(self, camera_id):
        self.events.append("manager:subscribe")
        return self.queue

    def get_latest_counts(self, camera_id):
        return {}

    def unsubscribe(self, camera_id, queue):
        self.events.append("manager:unsubscribe")


class FakeWebSocket:
    def __init__(
        self,
        *,
        cookies=None,
        origin="http://localhost:5173",
        host="localhost:8000",
        query=None,
        events=None,
        manager=None,
    ):
        self.events = events if events is not None else []
        self.cookies = cookies or {}
        self.headers = {"host": host}
        if origin:
            self.headers["origin"] = origin
        self.query_params = query or {}
        self.url = SimpleNamespace(scheme="ws")
        self.app = SimpleNamespace(state=SimpleNamespace(camera_manager=manager))
        self.accepted = False
        self.close_events = []

    async def close(self, code=1000, reason=None):
        self.events.append("close")
        self.close_events.append((code, reason))

    async def accept(self):
        self.events.append("accept")
        self.accepted = True

    async def send_text(self, text):
        self.events.append("send")


class RevokingWebSocket(FakeWebSocket):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    async def accept(self):
        self.user.token_version += 1
        await super().accept()


async def test_active_media_session_detects_revocation_and_deactivation(monkeypatch):
    user = SimpleNamespace(
        id=1,
        is_active=True,
        must_change_password=False,
        token_version=3,
    )
    fake_db = FakeDB(user, None, [])
    monkeypatch.setattr(stream, "AsyncSessionLocal", lambda: fake_db)

    assert await stream._media_session_is_current(user.id, 3) is True
    user.token_version += 1
    assert await stream._media_session_is_current(user.id, 3) is False
    user.token_version = 3
    user.is_active = False
    assert await stream._media_session_is_current(user.id, 3) is False


@pytest.mark.parametrize("token", ["", "not-a-jwt"])
async def test_websocket_rejects_missing_or_invalid_media_cookie_before_accept(monkeypatch, token):
    user = SimpleNamespace(id=1, is_active=True, must_change_password=False, token_version=0)
    camera = SimpleNamespace(id=5)
    events = []
    manager = FakeManager(events, [True])
    fake_db = FakeDB(user, camera, events)
    monkeypatch.setattr(stream, "AsyncSessionLocal", lambda: fake_db)
    socket = FakeWebSocket(
        cookies={media_cookie_name(): token} if token else {},
        query={"token": create_access_token("1", token_type="media")},
        events=events,
        manager=manager,
    )

    await stream.websocket_stream(socket, 5)
    assert socket.accepted is False
    assert socket.close_events
    assert "accept" not in events


async def test_websocket_rejects_cross_origin_before_authentication():
    socket = FakeWebSocket(origin="https://attacker.invalid")
    await stream.websocket_stream(socket, 5)
    assert socket.accepted is False
    assert socket.close_events[0][1] == "Untrusted origin"


async def test_websocket_accepts_same_origin_dashboard_served_by_backend(monkeypatch):
    user = SimpleNamespace(id=1, is_active=True, must_change_password=False, token_version=0)
    camera = SimpleNamespace(id=5)
    events = []
    manager = FakeManager(events, [True, False])
    monkeypatch.setattr(stream, "AsyncSessionLocal", lambda: FakeDB(user, camera, events))
    token = create_access_token("1", token_type="media", token_version=0)
    socket = FakeWebSocket(
        origin="http://localhost:8000",
        host="localhost:8000",
        cookies={media_cookie_name(): token},
        events=events,
        manager=manager,
    )

    await stream.websocket_stream(socket, 5)

    assert socket.accepted is True
    assert "manager:subscribe" in events
    assert "manager:unsubscribe" in events


async def test_websocket_rejects_disabled_user_before_accept(monkeypatch):
    user = SimpleNamespace(id=1, is_active=False, must_change_password=False, token_version=0)
    camera = SimpleNamespace(id=5)
    events = []
    manager = FakeManager(events, [True])
    fake_db = FakeDB(user, camera, events)
    monkeypatch.setattr(stream, "AsyncSessionLocal", lambda: fake_db)
    token = create_access_token("1", token_type="media", token_version=0)
    socket = FakeWebSocket(cookies={media_cookie_name(): token}, events=events, manager=manager)

    await stream.websocket_stream(socket, 5)
    assert socket.accepted is False
    assert socket.close_events[0][1] == "Invalid session or camera"
    assert "manager:is_running" not in events


async def test_websocket_accepts_only_after_all_auth_checks(monkeypatch):
    user = SimpleNamespace(id=1, is_active=True, must_change_password=False, token_version=0)
    camera = SimpleNamespace(id=5)
    events = []
    manager = FakeManager(events, [True, False])
    fake_db = FakeDB(user, camera, events)
    monkeypatch.setattr(stream, "AsyncSessionLocal", lambda: fake_db)
    token = create_access_token("1", token_type="media", token_version=0)
    socket = FakeWebSocket(cookies={media_cookie_name(): token}, events=events, manager=manager)

    await stream.websocket_stream(socket, 5)
    assert socket.accepted is True
    assert events.index("db:User") < events.index("accept")
    assert events.index("db:Camera") < events.index("accept")
    assert events.index("manager:is_running") < events.index("accept")


async def test_active_websocket_closes_after_session_revocation(monkeypatch):
    user = SimpleNamespace(id=1, is_active=True, must_change_password=False, token_version=0)
    camera = SimpleNamespace(id=5)
    events = []
    manager = FakeManager(events, [True, True])
    fake_db = FakeDB(user, camera, events)
    monkeypatch.setattr(stream, "AsyncSessionLocal", lambda: fake_db)
    monkeypatch.setattr(stream, "MEDIA_SESSION_REVALIDATE_SECONDS", 0)
    token = create_access_token("1", token_type="media", token_version=0)
    socket = RevokingWebSocket(
        user=user,
        cookies={media_cookie_name(): token},
        events=events,
        manager=manager,
    )

    await stream.websocket_stream(socket, 5)

    assert socket.accepted is True
    assert socket.close_events == [(1008, "Media session revoked")]
    assert "manager:unsubscribe" in events
