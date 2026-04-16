"""
AnalysisFrame ORM model — a single chunk-level analysis result within a session.
Each frame stores speaker identity, detected emotion, and depression score.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnalysisFrame(Base):
    __tablename__ = "analysis_frames"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Parent Session ───────────────────────────────────────────
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Chunk Identification ─────────────────────────────────────
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Speaker Information ──────────────────────────────────────
    speaker: Mapped[str] = mapped_column(
        String(20), nullable=False  # "doctor" | "patient" | "unknown"
    )
    segment_start: Mapped[float] = mapped_column(Float, nullable=False)
    segment_end: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Emotion Analysis ─────────────────────────────────────────
    emotion: Mapped[str] = mapped_column(String(50), nullable=False)
    emotion_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    emotion_distribution: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    transcript: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ── Depression Score ─────────────────────────────────────────
    depression_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    # ── Audio Features ───────────────────────────────────────────
    rms_energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speaking_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Relationships ────────────────────────────────────────────
    session: Mapped["Session"] = relationship(
        "Session", back_populates="analysis_frames"
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisFrame chunk={self.chunk_index} "
            f"speaker={self.speaker} emotion={self.emotion}>"
        )
