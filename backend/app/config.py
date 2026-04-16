"""
Application configuration loaded from environment variables.
Uses pydantic-settings for type-safe config with .env file support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings — all values can be overridden via env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "VoiceEmotionAPI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/voice_emotion_db"

    # ── JWT Auth ─────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Audio ────────────────────────────────────────────────────
    AUDIO_STORAGE_PATH: str = "./audio_storage"

    # ── ML Models & Diarization ──────────────────────────────────
    HF_AUTH_TOKEN: str = ""

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the JSON string of CORS origins into a Python list."""
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5173"]

    @property
    def audio_dir(self) -> Path:
        """Return the audio storage directory, creating it if needed."""
        path = Path(self.AUDIO_STORAGE_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Singleton instance — import this everywhere
settings = Settings()
