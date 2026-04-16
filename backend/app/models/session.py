"""
Session ORM model — a single psychiatric recording session.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Integer, text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Foreign Keys ─────────────────────────────────────────────
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Session Metadata ─────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Analysis Summary ─────────────────────────────────────────
    final_depression_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    dominant_emotion: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Audio File Reference ─────────────────────────────────────
    audio_file_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    audio_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    audio_sample_rate: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=16000
    )
    audio_channels: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=1
    )
    audio_format: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default="wav"
    )
    audio_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # ── Flexible Metadata ────────────────────────────────────────
    session_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=dict
    )

    # ── Relationships ────────────────────────────────────────────
    doctor: Mapped["User"] = relationship(
        "User", back_populates="sessions"
    )
    patient: Mapped["Patient"] = relationship(
        "Patient", back_populates="sessions"
    )
    analysis_frames: Mapped[List["AnalysisFrame"]] = relationship(
        "AnalysisFrame", back_populates="session", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Session {self.id} status={self.status}>"
