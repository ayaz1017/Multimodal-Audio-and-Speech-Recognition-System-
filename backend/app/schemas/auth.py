"""
Pydantic schemas for authentication endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request Schemas ──────────────────────────────────────────────
class UserRegister(BaseModel):
    """POST /auth/register request body."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="doctor", pattern="^(doctor|admin)$")


class UserLogin(BaseModel):
    """POST /auth/login request body."""
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """POST /auth/refresh request body."""
    refresh_token: str


# ── Response Schemas ─────────────────────────────────────────────
class TokenResponse(BaseModel):
    """Successful authentication response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User data returned in API responses."""
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Combined auth response with tokens + user info."""
    user: UserResponse
    tokens: TokenResponse
