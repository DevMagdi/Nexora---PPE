from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.routes import stream
from app.core.auth import hash_password, media_cookie_name
from app.db.models import Base, Camera, User
from app.db.session import get_db
from app.main import FRONTEND_DIST, create_app

CAMERA_ID = 4


@asynccontextmanager
async def _noop_lifespan(_: FastAPI):
    """بدل الـ lifespan الحقيقي (migrations + تحميل الموديلات)."""
    yield


def _tiny_jpeg() -> bytes:
    array = np.zeros((48, 64, 3), dtype=np.uint8)
    array[:, :, 0] = 200
    ok, buffer = cv2.imencode(".jpg", array)
    assert ok
    return buffer.tobytes()


class LiveFakeManager:
    """Manager بديل بسيط: كاميرا شغالة بفريم جاهز وأرقام ثابتة.

    ``running_calls`` بتخلي ``is_running`` يقفل البث بعد عدد ندوات محدد
    عشان اختبار MJPEG يخلص بدل ما يفضل مفتوح للأنهاية.
    """

    def __init__(
        self,
        frame: bytes,
        running: bool = True,
        counts: dict | None = None,
        running_calls: list[bool] | None = None,
    ) -> None:
        self.frame = frame
        self.running = running
        self.counts = counts if counts is not None else {"person": 2, "no_mask": 1}
        self.running_calls = list(running_calls) if running_calls is not None else []
        self.subscribed = 0
        self.unsubscribed = 0

    def is_running(self, camera_id: int) -> bool:
        if self.running_calls:
            return self.running_calls.pop(0)
        return self.running

    def get_latest_frame(self, camera_id: int) -> bytes | None:
        return self.frame

    def get_latest_frame_with_seq(self, camera_id: int) -> tuple[bytes | None, int]:
        return self.frame, 1

    def get_latest_counts(self, camera_id: int) -> dict | None:
        return dict(self.counts)

    def subscribe(self, camera_id: int) -> asyncio.Queue:
        self.subscribed += 1
        return asyncio.Queue()

    def unsubscribe(self, camera_id: int, q: asyncio.Queue) -> None:
        self.unsubscribed += 1

    def active_count(self) -> int:
        return 1 if self.running else 0

    def counts_snapshot(self) -> dict[str, dict]:
        return {str(CAMERA_ID): dict(self.counts)} if self.running else {}

    def update_enabled_classes(self, camera_id: int, enabled_classes: list[str] | None) -> None:
        return None


class _PatchedSessionLocal:
    """يحوّل ``AsyncSessionLocal()`` لجلسة الاختبار المشتركة."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _PatchedSessionLocal:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded_db(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                sector="both",
                role="admin",
                is_active=True,
                must_change_password=False,
                token_version=0,
            )
        )
        session.add(
            User(
                username="med",
                password_hash=hash_password("medpass123"),
                sector="medical",
                role="viewer",
                is_active=True,
                must_change_password=False,
                token_version=0,
            )
        )
        session.add(
            Camera(
                id=CAMERA_ID,
                name="Medical Cam",
                source_type="webcam",
                source_uri="0",
                profile="medical",
                enabled_classes=[],
                is_active=True,
            )
        )
        session.add(
            Camera(
                id=5,
                name="Construction Cam",
                source_type="webcam",
                source_uri="1",
                profile="construction",
                enabled_classes=[],
                is_active=False,
            )
        )
        await session.commit()
        yield session


@pytest.fixture
def app(seeded_db: AsyncSession, engine, monkeypatch) -> FastAPI:
    monkeypatch.setattr(stream, "AsyncSessionLocal", _PatchedSessionLocal(seeded_db))

    application = create_app()
    application.router.lifespan_context = _noop_lifespan

    async def override_db():
        yield seeded_db

    application.dependency_overrides[get_db] = override_db
    application.state.detectors = {"construction": object(), "medical": object()}
    application.state.camera_manager = LiveFakeManager(_tiny_jpeg())
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # من غير context manager عشان الـ lifespan (migrations/models) ميتشغلش
    # — بنغطّي الحالات اللي بيجهزها يدويًا في fixture أعلاه.
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        yield c



def _expect_ws_rejection(client: TestClient, url: str, headers: dict) -> tuple[int, str]:
    """يجبر مصافحة WebSocket أن تكتمل ثم يعيد (code, reason) من الرفض."""
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect(url, headers=headers),
    ):
        pass
    return exc_info.value.code, exc_info.value.reason

def _login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200


def _ws_cookie_header(client: TestClient) -> str:
    token = client.cookies.get(media_cookie_name(), "")
    assert token, "media cookie must exist after login"
    return f"{media_cookie_name()}={token}"


def test_login_then_media_token_then_mjpeg_then_websocket_e2e(app: FastAPI, client: TestClient) -> None:
    """دورة اللاوج الكاملة: تسجيل → توكن ميديا → MJPEG → WebSocket."""
    _login(client)
    assert client.cookies.get(media_cookie_name())

    renewed = client.post("/api/v1/auth/media-token")
    assert renewed.status_code == 204
    assert client.cookies.get(media_cookie_name())

    # 1) MJPEG: أول فريم يوصل فورًا مع multipart boundary
    #    (المانجر بيوقف البث بعد الندوة التالتة لـ is_running عشان الاختبار يخلص)
    manager = LiveFakeManager(_tiny_jpeg(), running_calls=[True, True, False])
    app.state.camera_manager = manager
    response = client.get(f"/api/v1/stream/{CAMERA_ID}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert b"--frame" in response.content
    assert b"\xff\xd8" in response.content  # JPEG SOI marker

    # 2) WebSocket من نفس الأصل (صفحة على localhost و API على 127.0.0.1 —
    #    سيناريو اللوج اللي كان بيرجع 403) بيتقبل ويرسل الأرقام فورًا
    with client.websocket_connect(
        f"/api/v1/ws/{CAMERA_ID}",
        headers={
            "origin": "http://testserver",
            "cookie": _ws_cookie_header(client),
        },
    ) as websocket:
        counts = websocket.receive_json()
        assert counts["person"] == 2
        assert counts["no_mask"] == 1


def test_websocket_accepts_exact_same_origin(client: TestClient) -> None:
    _login(client)
    with client.websocket_connect(
        f"/api/v1/ws/{CAMERA_ID}",
        headers={
            "origin": "http://testserver",
            "cookie": _ws_cookie_header(client),
        },
    ) as websocket:
        assert websocket.receive_json()["person"] == 2


def test_websocket_rejects_cross_origin_before_accept(client: TestClient) -> None:
    _login(client)
    code, reason = _expect_ws_rejection(
        client,
        f"/api/v1/ws/{CAMERA_ID}",
        headers={
            "origin": "https://attacker.invalid",
            "cookie": _ws_cookie_header(client),
        },
    )
    assert code == 1008
    assert reason == "Untrusted origin"


def test_websocket_rejects_missing_media_session(app: FastAPI, client: TestClient) -> None:
    _login(client)
    # عميل تاني بدون كوكيز الجلسة نهائيًا
    fresh = TestClient(app, base_url="http://127.0.0.1:8000")
    code, reason = _expect_ws_rejection(
        fresh,
        f"/api/v1/ws/{CAMERA_ID}",
        headers={"origin": "http://testserver"},
    )
    assert code == 1008
    assert reason == "Invalid or missing media session"


def test_websocket_rejects_when_camera_not_running(app: FastAPI, client: TestClient) -> None:
    _login(client)
    app.state.camera_manager = LiveFakeManager(_tiny_jpeg(), running=False)
    code, reason = _expect_ws_rejection(
        client,
        f"/api/v1/ws/{CAMERA_ID}",
        headers={
            "origin": "http://testserver",
            "cookie": _ws_cookie_header(client),
        },
    )
    assert code == 1008
    assert reason == "Camera not running"


def test_websocket_enforces_sector_isolation(engine, seeded_db: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(stream, "AsyncSessionLocal", _PatchedSessionLocal(seeded_db))
    application = create_app()
    application.router.lifespan_context = _noop_lifespan

    async def override_db():
        yield seeded_db

    application.dependency_overrides[get_db] = override_db
    application.state.detectors = {"construction": object(), "medical": object()}
    application.state.camera_manager = LiveFakeManager(_tiny_jpeg())

    with TestClient(application, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "med", "password": "medpass123"},
        )
        assert response.status_code == 200
        # مستخدم medical يحاول يفتح كاميرا construction → مرفوض قبل قبول الاتصال
        code, reason = _expect_ws_rejection(
            client,
            "/api/v1/ws/5",
            headers={
                "origin": "http://testserver",
                "cookie": _ws_cookie_header(client),
            },
        )
        assert code == 1008
        assert reason == "Forbidden"


def test_websocket_rejects_unknown_camera(client: TestClient) -> None:
    _login(client)
    code, reason = _expect_ws_rejection(
        client,
        "/api/v1/ws/9999",
        headers={
            "origin": "http://testserver",
            "cookie": _ws_cookie_header(client),
        },
    )
    assert code == 1008
    assert reason == "Invalid session or camera"


def test_mjpeg_rejected_when_camera_not_running(app: FastAPI, client: TestClient) -> None:
    _login(client)
    app.state.camera_manager = LiveFakeManager(_tiny_jpeg(), running=False)
    response = client.get(f"/api/v1/stream/{CAMERA_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Camera not running"


def test_mjpeg_requires_authentication(app: FastAPI) -> None:
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.get(f"/api/v1/stream/{CAMERA_ID}")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


class _LoopbackAliasManager(LiveFakeManager):
    pass


def test_full_origin_matrix_through_real_app(app: FastAPI, client: TestClient) -> None:
    """الأصل نفسه بيمرّ، انتحال الهوست/الدومينات الخارجية بترفض عبر التطبيق الحقيقي."""
    _login(client)
    cookie = _ws_cookie_header(client)

    for origin in ["http://testserver", "http://testserver/", "HTTP://TESTSERVER"]:
        with client.websocket_connect(
            f"/api/v1/ws/{CAMERA_ID}",
            headers={"origin": origin, "cookie": cookie},
        ) as websocket:
            assert websocket.receive_json()["person"] == 2

    for attacker_origin in [
        "https://attacker.invalid",
        "http://testserver.attacker.invalid",
        "http://testserver:8000.attacker.invalid",
        "null",
    ]:
        code, reason = _expect_ws_rejection(
            client,
            f"/api/v1/ws/{CAMERA_ID}",
            headers={"origin": attacker_origin, "cookie": cookie},
        )
        assert code == 1008
        assert reason == "Untrusted origin"


def test_spa_index_never_cached_and_assets_immutable(monkeypatch, tmp_path) -> None:
    """إصلاح الـ stale bundle: index.html ميتكاشش أبدًا."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>Nexora SPA</body></html>", encoding="utf-8")
    (dist / "assets" / "app.abc123.js").write_text("console.log('nexora')", encoding="utf-8")
    monkeypatch.setattr("app.main.FRONTEND_DIST", dist)

    application = create_app()
    application.router.lifespan_context = _noop_lifespan
    with TestClient(application, base_url="http://127.0.0.1:8000") as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "Nexora SPA" in index.text
        assert index.headers["cache-control"] == "no-store"

        asset = client.get("/assets/app.abc123.js")
        assert asset.status_code == 200
        assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"

        # مسارات SPA (client routing) برضه من غير كاش
        route = client.get("/live-view")
        assert route.status_code == 200
        assert route.headers["cache-control"] == "no-store"


def test_front_end_dist_constant_points_to_frontend_dir() -> None:
    from pathlib import Path

    assert FRONTEND_DIST == Path("app/main.py").resolve().parents[1] / "frontend" / "dist"
