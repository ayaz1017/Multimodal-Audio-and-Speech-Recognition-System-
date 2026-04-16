"""
Session routes — CRUD for sessions, analysis frame retrieval, and session lifecycle.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
import librosa
import time

from app.core.exceptions import NotFoundException
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.session import (
    AnalysisFrameResponse,
    SessionCreate,
    SessionEnd,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    summary="Create a new session",
)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Start a new psychiatric recording session for a patient.
    The session is created in 'active' status.
    """
    service = SessionService(db)
    return await service.create_session(data, current_user.id)


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List sessions",
)
async def list_sessions(
    patient_id: Optional[uuid.UUID] = Query(None, description="Filter by patient"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionListResponse:
    """
    List all sessions belonging to the authenticated doctor.
    Supports filtering by patient and status, with pagination.
    """
    service = SessionService(db)
    return await service.list_sessions(
        doctor_id=current_user.id,
        patient_id=patient_id,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get a single session",
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Retrieve a session by ID (must belong to the authenticated doctor)."""
    try:
        service = SessionService(db)
        return await service.get_session(session_id, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Update a session",
)
async def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Update session fields such as status, notes, or scores."""
    try:
        service = SessionService(db)
        return await service.update_session(session_id, data, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/{session_id}/end",
    response_model=SessionResponse,
    summary="End a session",
)
async def end_session(
    session_id: uuid.UUID,
    data: SessionEnd = SessionEnd(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Mark a session as completed. Calculates the session duration and
    sets status to 'completed'. Optionally add closing notes.
    """
    try:
        service = SessionService(db)
        return await service.end_session(session_id, data, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/{session_id}/frames",
    response_model=List[AnalysisFrameResponse],
    summary="Get analysis frames for a session",
)
async def get_analysis_frames(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AnalysisFrameResponse]:
    """
    Retrieve all emotion/depression analysis frames for a given session,
    ordered by chunk index. Used by the frontend to render timeline charts.
    """
    try:
        service = SessionService(db)
        return await service.get_analysis_frames(session_id, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/{session_id}",
    status_code=204,
    summary="Delete a session",
)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete a session and all associated analysis frames.
    This action cannot be undone.
    """
    try:
        service = SessionService(db)
        await service.delete_session(session_id, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/upload",
    response_model=SessionResponse,
    summary="Upload audio file for offline analysis",
)
async def upload_audio_session(
    patient_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Directly uploads an audio file (mp3/wav), bypasses microphone distortion,
    and runs highly accurate continuous ML inference.
    """
    import tempfile
    import os
    import subprocess

    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        ffmpeg_bin = None

    try:
        # Save raw encrypted payload (e.g. .opus)
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".opus"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        
        wav_path = tmp_path + ".wav"
            
        try:
            # WhatsApp uses .opus, which Mac CoreAudio cannot read seamlessly.
            # We use an internal headless FFmpeg binary to transcode exotic formats directly to pure AI-ready WAV.
            if ffmpeg_bin:
                subprocess.run(
                    [ffmpeg_bin, "-y", "-i", tmp_path, "-ar", "16000", "-ac", "1", wav_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                if os.path.exists(wav_path):
                    audio_data, sr = librosa.load(wav_path, sr=16000, mono=True)
                else:
                    audio_data, sr = librosa.load(tmp_path, sr=16000, mono=True)
            else:
                # Standard CoreAudio fallback for generic formats
                audio_data, sr = librosa.load(tmp_path, sr=16000, mono=True)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(wav_path):
                os.remove(wav_path)
                
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode audio format (Ensure it is a valid sound file): {e}")

    # Create session
    service = SessionService(db)
    session = await service.create_session(
        SessionCreate(patient_id=patient_id), current_user.id
    )
    from app.models.analysis_frame import AnalysisFrame
    from app.services.audio_utils import apply_spectral_gating
    from app.services.audio_pipeline import AudioPipeline
    
    # ── Unify processing using the authentic AudioPipeline ──
    pipeline = AudioPipeline(sample_rate=16000)
    
    # Process in 3-second chunks (48000 samples @ 16kHz)
    chunk_size = 16000 * 3
    total_chunks = len(audio_data) // chunk_size
    if total_chunks == 0 and len(audio_data) > 0:
        total_chunks = 1

    db_frames = []
    
    for i in range(total_chunks):
        start = i * chunk_size
        end = min((i + 1) * chunk_size, len(audio_data))
        chunk = audio_data[start:end]
        
        # Apply strict production filtering
        chunk = apply_spectral_gating(chunk, 16000)
        
        # Pad if extremely short
        if len(chunk) < chunk_size and len(chunk) > 0:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)), "constant")
            
        # ── Pipeline Execution ──
        # Process the numpy array natively, applying EMA smoothing & text overrides
        result = pipeline.process_chunk(chunk, chunk_index=i, force_patient=True)
        
        frame = AnalysisFrame(
            session_id=session.id,
            chunk_index=i,
            speaker=result.speaker,
            segment_start=float(i * 3.0),
            segment_end=float((i + 1) * 3.0),
            emotion=result.emotion,
            emotion_confidence=result.emotion_confidence,
            emotion_distribution=result.emotion_distribution,
            transcript=result.transcript,
            depression_score=result.depression_score,
            rms_energy=float(np.sqrt(np.mean(chunk**2))),
        )
        db.add(frame)
        
        # track valid frames
        is_silence_flag = float(np.sqrt(np.mean(chunk**2))) < 0.005
        db_frames.append((frame, is_silence_flag))

    # Save frames
    await db.commit()
    
    # Calculate dominant emotion
    valid_frames = [f[0] for f in db_frames if not f[1]]
    final_score = pipeline.get_session_summary().get("rolling_depression_avg", 0.0)

    if valid_frames:
        from collections import Counter
        emotions = [f.emotion for f in valid_frames if f.emotion]
        dominant = Counter(emotions).most_common(1)[0][0] if emotions else "neutral"
    else:
        dominant = "neutral"

    # End session with authentic scores
    return await service.end_session(
        session.id, 
        SessionEnd(
            notes=f"File '{file.filename}' processed offline ({len(valid_frames)} active chunks).",
            final_depression_score=float(final_score),
            dominant_emotion=dominant
        ),
        current_user.id
    )
