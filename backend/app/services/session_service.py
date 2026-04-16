"""
Session service — manages psychiatric session lifecycle, audio metadata,
and analysis frame storage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.analysis_frame import AnalysisFrame
from app.models.session import Session
from app.schemas.session import (
    AnalysisFrameResponse,
    SessionCreate,
    SessionEnd,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)


class SessionService:
    """Encapsulates all session management business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create Session ───────────────────────────────────────────
    async def create_session(
        self, data: SessionCreate, doctor_id: uuid.UUID
    ) -> SessionResponse:
        """Create a new active session for a doctor-patient pair."""
        session = Session(
            doctor_id=doctor_id,
            patient_id=data.patient_id,
            status="active",
            notes=data.notes,
            session_metadata=data.session_metadata or {},
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return SessionResponse.from_orm_model(session)

    # ── Get Session ──────────────────────────────────────────────
    async def get_session(
        self, session_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> SessionResponse:
        """
        Retrieve a session by ID, scoped to the requesting doctor.

        Raises:
            NotFoundException: If session doesn't exist or belongs to another doctor.
        """
        session = await self._get_owned_session(session_id, doctor_id)
        return SessionResponse.from_orm_model(session)

    # ── List Sessions ────────────────────────────────────────────
    async def list_sessions(
        self,
        doctor_id: uuid.UUID,
        patient_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SessionListResponse:
        """List sessions for a doctor with optional filters and pagination."""
        query = (
            select(Session)
            .where(Session.doctor_id == doctor_id)
            .options(selectinload(Session.patient))
        )

        if patient_id:
            query = query.where(Session.patient_id == patient_id)
        if status:
            query = query.where(Session.status == status)

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = (
            query.order_by(Session.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        sessions = result.scalars().all()

        return SessionListResponse(
            sessions=[SessionResponse.from_orm_model(s) for s in sessions],
            total=total,
            page=page,
            page_size=page_size,
        )

    # ── Update Session ───────────────────────────────────────────
    async def update_session(
        self,
        session_id: uuid.UUID,
        data: SessionUpdate,
        doctor_id: uuid.UUID,
    ) -> SessionResponse:
        """Update session fields (status, notes, scores)."""
        session = await self._get_owned_session(session_id, doctor_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)

        await self.db.commit()
        await self.db.refresh(session)
        return SessionResponse.from_orm_model(session)

    # ── End Session ──────────────────────────────────────────────
    async def end_session(
        self,
        session_id: uuid.UUID,
        data: SessionEnd,
        doctor_id: uuid.UUID,
    ) -> SessionResponse:
        """
        Mark a session as completed, calculate duration, and optionally
        add final notes.
        """
        session = await self._get_owned_session(session_id, doctor_id)

        now = datetime.now(timezone.utc)
        session.status = "completed"
        session.ended_at = now
        session.duration_seconds = int(
            (now - session.started_at).total_seconds()
        )
        if data.notes:
            session.notes = data.notes

        await self.db.commit()
        await self.db.refresh(session)
        return SessionResponse.from_orm_model(session)

    # ── Audio Metadata ───────────────────────────────────────────
    async def save_audio_metadata(
        self,
        session_id: uuid.UUID,
        doctor_id: uuid.UUID,
        *,
        file_path: str,
        duration_seconds: float,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_format: str = "wav",
        size_bytes: int = 0,
    ) -> SessionResponse:
        """Attach audio file metadata to a session after recording."""
        session = await self._get_owned_session(session_id, doctor_id)

        session.audio_file_path = file_path
        session.audio_duration_seconds = duration_seconds
        session.audio_sample_rate = sample_rate
        session.audio_channels = channels
        session.audio_format = audio_format
        session.audio_size_bytes = size_bytes

        await self.db.commit()
        await self.db.refresh(session)
        return SessionResponse.from_orm_model(session)

    # ── Analysis Frames ──────────────────────────────────────────
    async def save_analysis_frame(
        self,
        session_id: uuid.UUID,
        chunk_index: int,
        speaker: str,
        segment_start: float,
        segment_end: float,
        emotion: str,
        emotion_confidence: float,
        emotion_distribution: Optional[Dict[str, Any]] = None,
        transcript: Optional[str] = None,
        depression_score: Optional[float] = None,
        rms_energy: Optional[float] = None,
        speaking_rate: Optional[float] = None,
    ) -> AnalysisFrame:
        """Persist a single analysis frame to the database."""
        frame = AnalysisFrame(
            session_id=session_id,
            chunk_index=chunk_index,
            speaker=speaker,
            segment_start=segment_start,
            segment_end=segment_end,
            emotion=emotion,
            emotion_confidence=emotion_confidence,
            emotion_distribution=emotion_distribution,
            transcript=transcript,
            depression_score=depression_score,
            rms_energy=rms_energy,
            speaking_rate=speaking_rate,
        )
        self.db.add(frame)
        await self.db.commit()
        await self.db.refresh(frame)
        return frame

    async def get_analysis_frames(
        self, session_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> List[AnalysisFrameResponse]:
        """Retrieve all analysis frames for a session, ordered by chunk index."""
        # Verify ownership
        await self._get_owned_session(session_id, doctor_id)

        result = await self.db.execute(
            select(AnalysisFrame)
            .where(AnalysisFrame.session_id == session_id)
            .order_by(AnalysisFrame.chunk_index)
        )
        frames = result.scalars().all()
        return [AnalysisFrameResponse.model_validate(f) for f in frames]

    # ── Delete Session ───────────────────────────────────────────
    async def delete_session(
        self, session_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> None:
        """Delete a session and all its analysis frames (cascade)."""
        import os
        session = await self._get_owned_session(session_id, doctor_id)
        
        # Physical cleanup of audio files if they exist
        if session.audio_file_path and os.path.exists(session.audio_file_path):
            try:
                os.remove(session.audio_file_path)
            except Exception as e:
                # Log but don't block DB deletion if file cleanup fails
                from app.services.session_service import logger
                logger.error(f"Failed to delete session audio file: {e}")
        
        await self.db.delete(session)
        await self.db.commit()

    # ── Internal Helpers ─────────────────────────────────────────
    async def _get_owned_session(
        self, session_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> Session:
        """Fetch a session, ensuring it belongs to the requesting doctor."""
        result = await self.db.execute(
            select(Session)
            .where(
                Session.id == session_id,
                Session.doctor_id == doctor_id,
            )
            .options(selectinload(Session.patient))
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundException("Session", str(session_id))
        return session
