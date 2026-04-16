"""
Audio routes — serving recorded session files.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.core.security import decode_access_token
from app.services.auth_service import AuthService
from app.services.session_service import SessionService

router = APIRouter(prefix="/audio", tags=["Audio"])


@router.get(
    "/session/{session_id}",
    summary="Download or stream a session recording",
)
async def get_session_audio(
    session_id: uuid.UUID,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the full merged WAV recording for a specific session.
    Supports query-param token auth so <audio> and wavesurfer can load it directly.
    """
    # ── Auth via query param (required for browser audio/wavesurfer) ──
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # ── Verify session ownership ──────────────────────────────────────
    service = SessionService(db)
    try:
        await service.get_session(session_id, user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")

    # ── Locate the merged WAV file ────────────────────────────────────
    # Try standard path first (UUID format with dashes)
    file_path = settings.audio_dir / str(session_id) / "full_session.wav"

    # Fallback: use the path stored in the session record itself
    if not file_path.exists():
        try:
            session_obj = await service.get_session(session_id, user.id)
            if session_obj and hasattr(session_obj, "audio_file_path") and session_obj.audio_file_path:
                stored = Path(session_obj.audio_file_path)
                # stored path may be relative to backend root
                if not stored.is_absolute():
                    stored = Path("/Users/yash/claude_app/backend") / stored
                if stored.exists():
                    file_path = stored
        except Exception:
            pass

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Recording not available yet. The session may still be processing."
        )

    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"session_{session_id}.wav",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }
    )
