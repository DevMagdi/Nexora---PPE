from __future__ import annotations

import asyncio
import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.auth import ensure_jwt_secret_strength, get_current_user_media
from app.core.config import settings
from app.core.logging import configure_root_logger, get_logger
from app.db.driver_hints import database_backend_label, database_startup_hint
from app.db.models import Camera, User
from app.db.session import get_db, init_db

logger = get_logger(__name__)

_FRAME_PATH_RE = re.compile(r"^camera_(\d+)/[A-Za-z0-9_.-]+\.jpg$")
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _upgrade_database_sync() -> None:
    """Apply versioned schema changes before serving requests."""
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        # Surface missing DB drivers / bad URLs as an actionable message instead
        # of a raw SQLAlchemy traceback (e.g. MSSQL without aioodbc/pyodbc).
        raise RuntimeError(database_startup_hint(settings.DATABASE_URL, exc)) from exc


async def upgrade_database() -> None:
    await asyncio.to_thread(_upgrade_database_sync)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_root_logger(settings.LOG_LEVEL)
    logger.info("Starting Mantik PPE API (env=%s)", settings.APP_ENV)
    logger.info("Database backend: %s", database_backend_label(settings.DATABASE_URL))
    # Fail fast with a clear message instead of PyJWT's InsecureKeyLengthWarning
    # surfacing later at the first login/media request.
    ensure_jwt_secret_strength()

    if settings.APP_ENV == "dev" and "JWT_SECRET" not in settings.model_fields_set:
        logger.warning(
            "JWT_SECRET is unset; this development key is ephemeral and access/media sessions "
            "will be invalidated after a backend restart. Set JWT_SECRET in .env with "
            "`python scripts/gen_jwt_secret.py` for stable local sessions."
        )

    if settings.APP_ENV == "dev" and "BOOTSTRAP_PASSWORD" not in settings.model_fields_set:
        logger.warning(
            "Development bootstrap credentials (dev only): %s / %s",
            settings.BOOTSTRAP_USERNAME,
            settings.BOOTSTRAP_PASSWORD,
        )

    from app.core.detector import PPEDetector

    logger.info("Loading the approved industrial PPE checkpoint...")
    # Fail closed if the exact artifact is absent or its class contract is invalid.
    app.state.detector = await asyncio.to_thread(PPEDetector)

    os.makedirs(settings.FRAMES_DIR, exist_ok=True)

    # Fail closed: schema updates are versioned and applied before the app starts.
    logger.info("Applying database migrations...")
    try:
        await upgrade_database()
    except Exception:
        logger.exception(
            "Database migration failed; API startup is stopping before camera initialization."
        )
        raise
    logger.info("Database migrations applied")
    logger.info("Verifying application database connection and schema...")
    try:
        await init_db()
    except Exception:
        logger.exception(
            "Database schema verification failed after Alembic; API startup is stopping."
        )
        raise
    logger.info("Database schema is up to date")

    from app.db.repository import ensure_bootstrap_user

    logger.info("Ensuring bootstrap admin user...")
    await ensure_bootstrap_user(
        username=settings.BOOTSTRAP_USERNAME,
        password=settings.BOOTSTRAP_PASSWORD,
    )
    logger.info("Bootstrap user check complete")

    if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").is_file():
        logger.info("Frontend bundle found — SPA will be served from %s", FRONTEND_DIST)
    else:
        logger.info(
            "Frontend bundle not found — API-only mode "
            "(dev docs at /docs, dashboard via `npm run dev` in frontend/)"
        )

    from app.camera.manager import CameraManager

    logger.info("Starting camera manager...")
    app.state.camera_manager = CameraManager(app.state.detector)
    await app.state.camera_manager.start()
    logger.info("Camera manager started — API is ready")

    yield

    logger.info("Shutting down camera manager...")
    await app.state.camera_manager.stop()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mantik Industrial PPE API",
        description="Industrial safety monitoring for factories, construction sites, workshops and warehouses",
        version="4.0.0",
        lifespan=lifespan,
        docs_url=None if settings.APP_ENV == "prod" else "/docs",
        redoc_url=None if settings.APP_ENV == "prod" else "/redoc",
        openapi_url=None if settings.APP_ENV == "prod" else "/openapi.json",
    )

    app.state.inference_slots = asyncio.Semaphore(2)
    app.state.login_rate_limiter = None
    from app.core.rate_limit import SlidingWindowRateLimiter

    app.state.login_rate_limiter = SlidingWindowRateLimiter(
        settings.LOGIN_RATE_LIMIT,
        settings.LOGIN_RATE_WINDOW_SECONDS,
    )

    from app.api.upload_limit import UploadLimitMiddleware

    app.add_middleware(UploadLimitMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        max_age=600,
    )

    @app.middleware("http")
    async def secure_http_responses(request: Request, call_next):
        if (
            settings.APP_ENV == "prod"
            and request.url.scheme != "https"
            and request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
            != "https"
        ):
            return JSONResponse(status_code=400, content={"detail": "HTTPS is required"})

        origin = request.headers.get("origin")
        if (
            settings.APP_ENV == "prod"
            and origin
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and origin.rstrip("/") not in settings.cors_origins
        ):
            return JSONResponse(status_code=403, content={"detail": "Untrusted request origin"})

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if settings.APP_ENV != "dev":
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.APP_ENV != "dev":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; base-uri 'self'; object-src 'none'; "
                "frame-ancestors 'none'; form-action 'self'; "
                "img-src 'self' data: blob:; font-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; script-src 'self'; "
                "connect-src 'self' ws: wss:"
            )
        if settings.APP_ENV == "prod":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith(("/api/", "/frames/")):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.startswith("/assets/"):
            # Vite emits content-hashed filenames, so they are safe to cache
            # forever; index.html (below) must never be cached or browsers
            # keep booting a stale bundle after every redeploy.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif "." not in request.url.path.rsplit("/", 1)[-1]:
            # SPA routes (and index.html itself) must always revalidate so the
            # browser immediately picks up newly deployed bundles.
            response.headers["Cache-Control"] = "no-store"
        return response

    from app.api.routes.dashboard import router as dashboard_router
    from app.api.routes.inference import router as inference_router
    from app.api.routes.sites import router as sites_router

    for router in (dashboard_router, inference_router, sites_router):
        app.include_router(router, prefix="/api/v1")
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
        match = _FRAME_PATH_RE.fullmatch(normalized)
        if not match or "\x00" in normalized:
            raise HTTPException(status_code=404, detail="Frame not found")

        camera = await db.get(Camera, int(match.group(1)))
        if camera is None:
            raise HTTPException(status_code=404, detail="Frame not found")

        base_dir = Path(settings.FRAMES_DIR).resolve()
        try:
            resolved = (base_dir / normalized).resolve(strict=True)
            resolved.relative_to(base_dir)
        except (OSError, RuntimeError, ValueError):
            raise HTTPException(status_code=404, detail="Frame not found") from None
        if not resolved.is_file():
            raise HTTPException(status_code=404, detail="Frame not found")

        return FileResponse(
            resolved,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").is_file():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            if full_path.startswith(("api/", "frames/")):
                raise HTTPException(status_code=404, detail="Not Found")
            if full_path:
                candidate = (FRONTEND_DIST / full_path).resolve()
                if candidate.is_relative_to(FRONTEND_DIST.resolve()) and candidate.is_file():
                    return FileResponse(str(candidate))
            return FileResponse(str(FRONTEND_DIST / "index.html"))

    return app


app = create_app()
