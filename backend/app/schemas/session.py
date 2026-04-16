"""
Pydantic schemas for session endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────
class SessionCreate(BaseModel):
    """POST /sessions request body."""
    patient_id: uuid.UUID
    notes: Optional[str] = None
    session_metadata: Optional[Dict[str, Any]] = None


class SessionUpdate(BaseModel):
    """PUT /sessions/{id} request body."""
    status: Optional[str] = Field(None, pattern="^(active|completed|cancelled)$")
    notes: Optional[str] = None
    final_depression_score: Optional[float] = Field(None, ge=0, le=100)
    dominant_emotion: Optional[str] = None


class SessionEnd(BaseModel):
    """POST /sessions/{id}/end request body."""
    notes: Optional[str] = None


# ── Response Schemas ─────────────────────────────────────────────
class AudioMetadataResponse(BaseModel):
    """Audio file metadata embedded in session responses."""
    audio_file_path: Optional[str] = None
    audio_duration_seconds: Optional[float] = None
    audio_sample_rate: Optional[int] = None
    audio_channels: Optional[int] = None
    audio_format: Optional[str] = None
    audio_size_bytes: Optional[int] = None


class AnalysisFrameResponse(BaseModel):
    """Single analysis frame result."""
    id: uuid.UUID
    chunk_index: int
    timestamp: datetime
    speaker: str
    segment_start: float
    segment_end: float
    emotion: str
    emotion_confidence: float
    emotion_distribution: Optional[Dict[str, Any]] = None
    transcript: Optional[str] = None
    depression_score: Optional[float] = None
    rms_energy: Optional[float] = None
    speaking_rate: Optional[float] = None

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Session data returned in API responses."""
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: Optional[str] = None
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    final_depression_score: Optional[float] = None
    dominant_emotion: Optional[str] = None
    notes: Optional[str] = None
    audio_metadata: Optional[AudioMetadataResponse] = None
    session_metadata: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, session: Any) -> "SessionResponse":
        """Build response from ORM model, nesting audio metadata."""
        patient_name = session.patient.full_name if hasattr(session, "patient") and session.patient else None
        
        return cls(
            id=session.id,
            doctor_id=session.doctor_id,
            patient_id=session.patient_id,
            patient_name=patient_name,
            status=session.status,
            started_at=session.started_at,
            ended_at=session.ended_at,
            duration_seconds=session.duration_seconds,
            final_depression_score=session.final_depression_score,
            dominant_emotion=session.dominant_emotion,
            notes=session.notes,
            audio_metadata=AudioMetadataResponse(
                audio_file_path=session.audio_file_path,
                audio_duration_seconds=session.audio_duration_seconds,
                audio_sample_rate=session.audio_sample_rate,
                audio_channels=session.audio_channels,
                audio_format=session.audio_format,
                audio_size_bytes=session.audio_size_bytes,
            ),
            session_metadata=session.session_metadata,
        )


class SessionListResponse(BaseModel):
    """Paginated list of sessions."""
    sessions: List[SessionResponse]
    total: int
    page: int
    page_size: int
