"""
Async SQLAlchemy engine, session factory, and Base declarative class.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── Engine ───────────────────────────────────────────────────────
engine_args = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

# SQLite does not support pool_size or max_overflow
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_args["pool_size"] = 20
    engine_args["max_overflow"] = 10

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_args
)

# ── Session Factory ──────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative Base ─────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass
