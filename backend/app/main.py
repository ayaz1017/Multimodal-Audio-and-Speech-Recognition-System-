"""
FastAPI application factory and lifespan event management.

This is the main entry point for the Voice Emotion Detection API.
Run with:  uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.api.websocket.handler import router as ws_router, get_active_connection_count
from app.config import settings
from app.core.exceptions import AppException
from app.database import engine
from app.core.models import model_manager

# ── Logging ──────────────────────────────────────────────────────
# Root configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Silence noisy third-party libraries
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)


# ── Lifespan Events ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    - Startup: create tables (dev mode), ensure audio directory exists, pre-load models.
    - Shutdown: dispose the engine connection pool.
    """
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Pre-load heavy AI models to prevent 'stuck' connections later
    await model_manager.load_models()

    # Create tables in dev mode (use Alembic migrations in production)
    if settings.DEBUG:
        from app.database import Base
        # Import all models so Base.metadata knows about them
        import app.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (DEBUG mode)")

    # Ensure audio storage directory exists
    settings.audio_dir
    logger.info(f"Audio storage: {settings.AUDIO_STORAGE_PATH}")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Database engine disposed. Goodbye!")


# ── Application Factory ─────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Real-time AI-powered voice emotion detection API for psychiatric sessions. "
        "Provides WebSocket audio streaming, speaker diarization, emotion detection, "
        "and depression score calculation."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS Middleware ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handler ────────────────────────────────────
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Convert AppException subclasses into structured JSON error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "status_code": exc.status_code,
        },
    )


# ── Routes ───────────────────────────────────────────────────────
app.include_router(v1_router)
app.include_router(ws_router)


# ── Health Check ─────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    Returns application status and active WebSocket connection count.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "active_ws_connections": get_active_connection_count(),
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint — returns basic API information."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
