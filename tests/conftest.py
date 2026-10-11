from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import create_access_token, hash_password
from app.db.models import Base, User
from app.db.session import get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        username="admin",
        password_hash=hash_password("admin123"),
        sector="both",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_client(db_session: AsyncSession, test_user: User):
    from app.main import create_app

    app = create_app()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    mock_detector = MagicMock()
    mock_detector.detect.return_value = []

    mock_manager = MagicMock()
    mock_manager.is_running.return_value = False
    mock_manager.active_count.return_value = 0
    mock_manager.counts_snapshot.return_value = {}
    mock_manager.start = AsyncMock()
    mock_manager.stop = AsyncMock()
    mock_manager.start_camera = AsyncMock(return_value=True)
    mock_manager.stop_camera = AsyncMock(return_value=True)
    mock_manager.update_enabled_classes = MagicMock()
    mock_manager.get_latest_frame.return_value = None
    mock_manager.get_latest_frame_with_seq.return_value = (None, 0)
    mock_manager._entries = {}

    app.state.detectors = {
        "construction": mock_detector,
        "medical": mock_detector,
    }
    app.state.camera_manager = mock_manager

    token = create_access_token(sub=str(test_user.id))
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
    ) as client:
        yield client


@pytest.fixture
async def anon_client(db_session: AsyncSession):
    from app.main import create_app

    app = create_app()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
