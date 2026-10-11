from __future__ import annotations

import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_media
from app.core.config import settings
from app.core.logging import configure_root_logger, get_logger
from app.db.models import Camera, User
from app.db.session import get_db

logger = get_logger(__name__)

_CAMERA_FOLDER_RE = re.compile(r"^camera_(\d+)/")
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_root_logger(settings.LOG_LEVEL)
    logger.info("Starting PPE Detection API (env=%s)", settings.APP_ENV)

    if settings.APP_ENV == "prod":
        if settings.JWT_SECRET in ("CHANGE_ME_SUPER_SECRET", "CHANGE_ME_TO_A_STRONG_RANDOM_SECRET"):
            logger.warning(
                "SECURITY WARNING: JWT_SECRET is using a default placeholder in production!"
            )
        if settings.BOOTSTRAP_PASSWORD == "admin123":
            logger.warning(
                "SECURITY WARNING: BOOTSTRAP_PASSWORD is set to default 'admin123' in production!"
            )

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
            fallbacks=("Model/ppe.pt", "Model/ppe_construction.pt"),
        ),
        "medical": PPEDetector(
            settings.MEDICAL_MODEL_PATH,
            settings.MEDICAL_DETECTION_CONFIDENCE,
            settings.MEDICAL_DEFAULT_CLASS_CONF,
            settings.MEDICAL_CLASS_CONF_THRESHOLDS,
            fallbacks=(
                "Model/bestMedicalModel2.pt",
                "Model/bestMedicalModel.pt",
                "Model/ppe_medical.pt",
            ),
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
    from app.api.routes.cameras import router as cameras_router
    from app.api.routes.health import router as health_router
    from app.api.routes.meta import router as meta_router
    from app.api.routes.stream import router as stream_router
    from app.api.routes.violations import router as violations_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(meta_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(cameras_router, prefix="/api/v1")
    app.include_router(violations_router, prefix="/api/v1")
    app.include_router(stream_router, prefix="/api/v1")

    os.makedirs(settings.FRAMES_DIR, exist_ok=True)

    @app.get("/frames/{file_path:path}", tags=["frames"])
    async def get_violation_frame(
        file_path: str,
        user: User = Depends(get_current_user_media),
        db: AsyncSession = Depends(get_db),
    ):
        normalized = file_path.replace("\\", "/").lstrip("/")
        if not normalized or "\x00" in normalized:
            raise HTTPException(status_code=404, detail="Frame not found")

        base_dir = os.path.realpath(settings.FRAMES_DIR)
        resolved = os.path.realpath(os.path.join(base_dir, normalized))
        if os.path.commonpath([base_dir, resolved]) != base_dir or not os.path.isfile(resolved):
            raise HTTPException(status_code=404, detail="Frame not found")

        match = _CAMERA_FOLDER_RE.match(normalized)
        if match and user.sector != "both":
            camera_id = int(match.group(1))
            cam = await db.get(Camera, camera_id)
            if cam and cam.profile != user.sector:
                raise HTTPException(status_code=403, detail="Forbidden")

        return FileResponse(resolved, media_type="image/jpeg")

    # Serve built React frontend in production if frontend/dist is available
    if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").is_file():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            if full_path:
                candidate = (FRONTEND_DIST / full_path).resolve()
                if (
                    str(candidate).startswith(str(FRONTEND_DIST.resolve()))
                    and candidate.is_file()
                ):
                    return FileResponse(str(candidate))
            return FileResponse(str(FRONTEND_DIST / "index.html"))

    return app


app = create_app()
