"""
V1 API router — aggregates all v1 sub-routers into a single prefix.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.patients import router as patients_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.audio import router as audio_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(patients_router)
router.include_router(sessions_router)
router.include_router(audio_router)
