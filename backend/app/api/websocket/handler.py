"""
WebSocket handler for real-time audio streaming sessions.

Protocol:
  1. Client connects to  /ws/session/{session_id}?token=<JWT>
  2. Server validates the JWT and session ownership.
  3. Client sends binary audio frames (raw PCM, 16-bit 16kHz mono).
  4. Client can also send JSON text frames for control messages.
  5. Server acknowledges each chunk and pushes analysis results as JSON.
  6. Either side can close the connection to end the stream.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import AsyncSessionLocal
from app.models.session import Session
from app.models.user import User
from app.services.audio_pipeline import AudioPipeline
from app.services.audio_utils import (
    compute_rms_energy,
    get_audio_file_info,
    merge_audio_chunks,
    pcm_bytes_to_numpy,
    save_audio_chunk,
    validate_audio_data,
)
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# ── Active Connection Registry ───────────────────────────────────
# Maps session_id → WebSocket for tracking live connections.
active_connections: Dict[str, WebSocket] = {}


async def _authenticate_ws(token: Optional[str], db: AsyncSession) -> Optional[User]:
    """Validate a JWT token and return the associated user, or None."""
    if not token:
        return None

    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


async def _validate_session(
    session_id: uuid.UUID, doctor_id: uuid.UUID, db: AsyncSession
) -> Optional[Session]:
    """Check that the session exists and belongs to the requesting doctor."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.doctor_id == doctor_id,
        )
    )
    return result.scalar_one_or_none()


async def _send_json(ws: WebSocket, data: dict) -> None:
    """Send a JSON message to the client, catching connection errors."""
    try:
        await ws.send_json(data)
    except Exception:
        logger.warning("Failed to send JSON to WebSocket client")


@router.websocket("/ws/session/{session_id}")
async def websocket_audio_stream(
    websocket: WebSocket,
    session_id: uuid.UUID,
    token: Optional[str] = Query(None),
):
    """
    Real-time audio streaming endpoint.

    The client streams binary PCM audio chunks and receives JSON analysis
    results. Authentication is done via a JWT token passed as a query param.

    Connection flow:
      1. Authenticate via JWT
      2. Validate session ownership
      3. Enter the receive loop
      4. For each binary frame: save chunk, compute features, send ack
      5. For JSON text frames: handle control messages (pause/resume/end)
      6. On disconnect: merge audio, save metadata, update session
    """
    # ── 1. Accept the connection first ───────────────────────────
    await websocket.accept()
    from app.core.models import model_manager

    # ── 2. Check AI Engine Readiness ─────────────────────────────
    if not model_manager.is_ready():
        await _send_json(websocket, {
            "type": "status",
            "status": "initializing",
            "message": "AI Engine is warming up. Please wait...",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("WebSocket connected but AI not ready: session=%s", session_id)

    # ── 3. Authenticate ──────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        user = await _authenticate_ws(token, db)
        if not user:
            await _send_json(websocket, {
                "type": "error",
                "code": "AUTH_FAILED",
                "message": "Invalid or missing authentication token",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await websocket.close(code=4001, reason="Authentication failed")
            return

        # ── 4. Validate session ──────────────────────────────────
        session = await _validate_session(session_id, user.id, db)
        if not session:
            await _send_json(websocket, {
                "type": "error",
                "code": "SESSION_NOT_FOUND",
                "message": "Session not found or access denied",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await websocket.close(code=4004, reason="Session not found")
            return

    # ── 5. Register connection + init pipeline ──────────────────
    session_key = str(session_id)
    active_connections[session_key] = websocket
    chunk_index = 0
    total_frag_index = 0
    is_recording = True
    force_patient_mode = False
    
    # ── PCM Buffering State ──────────────────────────────────────
    # 16bit 16kHz mono = 32,000 bytes/sec. We want ~3s chunks = 96,000 bytes.
    pcm_buffer = bytearray()
    BUFFER_SIZE_BYTES = 96000 
    
    # Initialize the real-time audio processing pipeline for this session
    pipeline = AudioPipeline(sample_rate=16000, extract_pitch=True)

    await _send_json(websocket, {
        "type": "status",
        "status": "connected",
        "message": "AI Engine ready. Streaming started.",
        "session_id": session_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    logger.info("WebSocket connected: session=%s, user=%s", session_id, user.email)

    # ── 5. Main receive loop ───────────────────────────────────
    try:
        while True:
            message = await websocket.receive()

            # ── Binary frame: audio data ─────────────────────────
            if "bytes" in message and message["bytes"]:
                audio_data = message["bytes"]

                if not is_recording:
                    await _send_json(websocket, {
                        "type": "warning",
                        "message": "Recording is paused. Send 'resume' to continue.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    continue

                # Validate the incoming audio data
                if not validate_audio_data(audio_data):
                    await _send_json(websocket, {
                        "type": "error",
                        "code": "INVALID_AUDIO",
                        "message": "Audio data too short or malformed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    continue

                # Save the chunk to disk (raw fragment)
                save_audio_chunk(
                    audio_data=audio_data,
                    session_id=session_key,
                    chunk_index=total_frag_index,
                    suffix="_frag" # Mark as fragment
                )
                total_frag_index += 1

                # Accumulate in buffer
                pcm_buffer.extend(audio_data)

                # Only process when we have enough data (3 Seconds)
                if len(pcm_buffer) >= BUFFER_SIZE_BYTES:
                    # Run full audio processing pipeline on the accumulated 3s window
                    # We take exactly the buffer size to keep timing consistent
                    chunk_to_process = bytes(pcm_buffer[:BUFFER_SIZE_BYTES])
                    pcm_buffer = pcm_buffer[BUFFER_SIZE_BYTES:] # Keep remainder for next window

                    result = pipeline.process_chunk(chunk_to_process, chunk_index, force_patient=force_patient_mode)

                    # Persist the analysis frame with real ML results
                    async with AsyncSessionLocal() as db:
                        session_service = SessionService(db)
                        await session_service.save_analysis_frame(
                            session_id=session_id,
                            chunk_index=chunk_index,
                            speaker=result.speaker,
                            segment_start=chunk_index * result.duration_seconds,
                            segment_end=(chunk_index + 1) * result.duration_seconds,
                            emotion=result.emotion.label,
                            emotion_confidence=result.emotion.confidence,
                            emotion_distribution=result.emotion.distribution,
                            transcript=result.transcript,
                            depression_score=result.depression_score,
                            rms_energy=result.rms_energy,
                            speaking_rate=None,
                        )

                    # Send rich analysis result back to client
                    await _send_json(websocket, {
                        "type": "analysis_result",
                        "chunk_index": chunk_index,
                        "duration_seconds": round(result.duration_seconds, 3),
                        "bytes_received": BUFFER_SIZE_BYTES,
                        "speaker": result.speaker,
                        "emotion": result.emotion.to_dict(),
                        "depression_score": round(result.depression_score, 2),
                        "depression_category": result.depression_category,
                        "depression_trend": result.depression_trend,
                        "rolling_depression_avg": round(result.rolling_depression_avg, 2),
                        "dominant_session_emotion": result.dominant_session_emotion,
                        "features": {
                            "rms_energy": round(result.rms_energy, 6),
                            "spectral_centroid": round(result.features.spectral_centroid, 2),
                        },
                        "timing": {
                            "total_pipeline_ms": round(result.total_processing_time_ms, 2),
                        },
                        "live_metrics": result.to_dict()["live_metrics"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                    chunk_index += 1
                else:
                    # Optional: Send ACK for fragment received if needed for frontend "sync" status
                    pass

            # ── Text frame: control message ──────────────────────
            elif "text" in message and message["text"]:
                try:
                    control = json.loads(message["text"])
                except json.JSONDecodeError:
                    await _send_json(websocket, {
                        "type": "error",
                        "code": "INVALID_JSON",
                        "message": "Text messages must be valid JSON",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    continue

                action = control.get("action", "").lower()

                if action == "pause":
                    is_recording = False
                    await _send_json(websocket, {
                        "type": "status",
                        "status": "paused",
                        "message": "Recording paused",
                        "chunks_received": chunk_index,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif action == "resume":
                    is_recording = True
                    await _send_json(websocket, {
                        "type": "status",
                        "status": "recording",
                        "message": "Recording resumed",
                        "chunks_received": chunk_index,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif action == "set_demo_mode":
                    active = control.get("enabled", False)
                    force_patient_mode = active
                    logger.info("Demo mode (Force Patient) set to %s for session %s", active, session_key)
                    await _send_json(websocket, {
                        "type": "demo_mode_status",
                        "enabled": force_patient_mode,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif action == "end":
                    logger.info("Client requested session end: %s", session_id)
                    break

                elif action == "ping":
                    await _send_json(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                else:
                    await _send_json(websocket, {
                        "type": "error",
                        "code": "UNKNOWN_ACTION",
                        "message": "Unknown action: %s" % action,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception as e:
        logger.error("WebSocket error for session %s: %s", session_id, e, exc_info=True)
        try:
            await _send_json(websocket, {
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass

    # ── 6. Cleanup — merge audio and update session ─────────────
    finally:
        active_connections.pop(session_key, None)

        if chunk_index > 0:
            try:
                async with AsyncSessionLocal() as db:
                    session_service = SessionService(db)

                    # ── Merge audio chunks ────────────────────────
                    merged_path = merge_audio_chunks(session_key)
                    if merged_path:
                        file_info = get_audio_file_info(merged_path)
                        await session_service.save_audio_metadata(
                            session_id=session_id,
                            doctor_id=user.id,
                            file_path=str(merged_path),
                            duration_seconds=file_info.get("duration_seconds", 0.0),
                            sample_rate=file_info.get("sample_rate", 16000),
                            channels=file_info.get("channels", 1),
                            audio_format="wav",
                            size_bytes=file_info.get("size_bytes", 0),
                        )

                    # ── Compute final scores from analysis frames ─
                    from app.models.analysis_frame import AnalysisFrame as AF
                    from sqlalchemy import select as sa_select
                    result = await db.execute(
                        sa_select(AF).where(AF.session_id == session_id)
                    )
                    all_frames = result.scalars().all()

                    if all_frames:
                        # Average depression score across all patient frames
                        scores = [
                            f.depression_score for f in all_frames
                            if f.depression_score is not None and f.speaker == "patient"
                        ]
                        final_score = round(sum(scores) / len(scores), 2) if scores else 0.0

                        # Most frequent emotion across patient frames
                        emotion_counts: dict = {}
                        for f in all_frames:
                            if f.speaker == "patient" and f.emotion:
                                emotion_counts[f.emotion] = emotion_counts.get(f.emotion, 0) + 1
                        dominant = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"
                    else:
                        final_score = 0.0
                        dominant = "neutral"

                    # ── Persist final results to session record ────
                    from app.schemas.session import SessionUpdate
                    await session_service.update_session(
                        session_id=session_id,
                        data=SessionUpdate(
                            status="completed",
                            final_depression_score=final_score,
                            dominant_emotion=dominant,
                        ),
                        doctor_id=user.id,
                    )
                    # Also set ended_at via direct ORM since SessionUpdate may not expose it
                    from sqlalchemy import text as sa_text
                    await db.execute(
                        sa_text("UPDATE sessions SET ended_at = :ts WHERE id = :id"),
                        {"ts": datetime.now(timezone.utc).isoformat(), "id": str(session_id).replace("-", "")}
                    )
                    await db.commit()

                    logger.info(
                        "Session %s finalized: %d chunks, score=%.1f, dominant=%s",
                        session_id, chunk_index, final_score, dominant,
                    )

            except Exception as e:
                logger.error(
                    "Failed to finalize session %s: %s",
                    session_id, e, exc_info=True,
                )

        # Send final status before closing (client may already be gone)
        try:
            await _send_json(websocket, {
                "type": "status",
                "status": "ended",
                "message": "Session stream ended",
                "total_chunks": chunk_index,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await websocket.close()
        except Exception:
            pass

        logger.info("WebSocket cleanup complete: session=%s", session_id)


# ── Utility: get active connection count ─────────────────────────
def get_active_connection_count() -> int:
    """Return the number of currently active WebSocket connections."""
    return len(active_connections)
