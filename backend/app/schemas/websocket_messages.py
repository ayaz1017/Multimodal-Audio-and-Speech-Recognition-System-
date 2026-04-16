"""
Pydantic schemas for WebSocket message protocol.
Defines the typed messages exchanged between client and server over WS.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Client → Server Messages ────────────────────────────────────
class WSClientMessage(BaseModel):
    """Base schema for messages sent by the client over WebSocket."""
    type: str  # "audio_chunk" | "control"
    payload: Dict[str, Any] = {}


class WSAudioChunk(BaseModel):
    """Metadata accompanying a binary audio chunk."""
    chunk_index: int
    sample_rate: int = 16000
    channels: int = 1
    format: str = "pcm_s16le"


class WSControlMessage(BaseModel):
    """Control commands from the client."""
    action: str  # "start" | "pause" | "resume" | "end"


# ── Server → Client Messages ────────────────────────────────────
class WSSpeakerSegment(BaseModel):
    """A single speaker segment within an analysis result."""
    label: str  # "doctor" | "patient" | "unknown"
    start: float
    end: float
    emotion: str
    emotion_confidence: float
    emotion_distribution: Optional[Dict[str, float]] = None


class WSDepressionScore(BaseModel):
    """Depression score data within an analysis result."""
    current: float
    trend: str  # "increasing" | "decreasing" | "stable"
    window_avg_5min: Optional[float] = None


class WSSessionStats(BaseModel):
    """Aggregated session statistics."""
    patient_talk_ratio: float
    dominant_patient_emotion: str
    elapsed_seconds: float


class WSAnalysisResult(BaseModel):
    """Complete analysis result pushed to the client for one audio chunk."""
    type: str = "analysis_result"
    session_id: str
    chunk_index: int
    timestamp: datetime
    speakers: List[WSSpeakerSegment]
    depression_score: WSDepressionScore
    session_stats: WSSessionStats


class WSStatusMessage(BaseModel):
    """Status/error messages from the server."""
    type: str = "status"
    status: str  # "connected" | "recording" | "paused" | "ended" | "error"
    message: str
    timestamp: datetime


class WSErrorMessage(BaseModel):
    """Error message from the server."""
    type: str = "error"
    code: str
    message: str
    timestamp: datetime
