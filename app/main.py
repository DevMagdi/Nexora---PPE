from __future__ import annotations

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import configure_root_logger, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_root_logger(settings.LOG_LEVEL)
    logger.info("Starting PPE Detection API (env=%s)", settings.APP_ENV)

    os.makedirs(settings.FRAMES_DIR, exist_ok=True)

    # Init DB (create tables)
    from app.db.session import init_db
    await init_db()
    logger.info("Database initialised")

    # Bootstrap user (only if users table empty)
    from app.db.repository import ensure_bootstrap_user
    await ensure_bootstrap_user(
        username=settings.BOOTSTRAP_USERNAME,
        password=settings.BOOTSTRAP_PASSWORD,
        sector=settings.BOOTSTRAP_SECTOR,
    )

    # Load detectors (two models)
    from app.core.detector import PPEDetector
    app.state.detectors = {
        "construction": PPEDetector(
            settings.CONSTRUCTION_MODEL_PATH,
            settings.CONSTRUCTION_DETECTION_CONFIDENCE,
            settings.CONSTRUCTION_DEFAULT_CLASS_CONF,
            settings.CONSTRUCTION_CLASS_CONF_THRESHOLDS,
        ),
        "medical": PPEDetector(
            settings.MEDICAL_MODEL_PATH,
            settings.MEDICAL_DETECTION_CONFIDENCE,
            settings.MEDICAL_DEFAULT_CLASS_CONF,
            settings.MEDICAL_CLASS_CONF_THRESHOLDS,
        ),
    }
    logger.info("Detectors loaded (construction+medical)")

    # Start camera manager
    from app.camera.manager import CameraManager
    app.state.camera_manager = CameraManager(app.state.detectors)
    await app.state.camera_manager.start()
    logger.info("Camera manager started")

    yield

    logger.info("Shutting down camera manager...")
    await app.state.camera_manager.stop()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nexora PPE Detection API (Multi-Model)",
        description="Construction + Medical PPE compliance monitoring",
        version="3.0.0",
        lifespan=lifespan,
    )

    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.routes.auth import router as auth_router
    from app.api.routes.health import router as health_router
    from app.api.routes.cameras import router as cameras_router
    from app.api.routes.violations import router as violations_router
    from app.api.routes.stream import router as stream_router
    from app.api.routes.meta import router as meta_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(meta_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(cameras_router, prefix="/api/v1")
    app.include_router(violations_router, prefix="/api/v1")
    app.include_router(stream_router, prefix="/api/v1")

    os.makedirs(settings.FRAMES_DIR, exist_ok=True)
    app.mount("/frames", StaticFiles(directory=settings.FRAMES_DIR), name="frames")

    return app


app = create_app()