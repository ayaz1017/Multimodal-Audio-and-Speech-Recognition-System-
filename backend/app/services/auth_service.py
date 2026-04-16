"""
Authentication service — handles user registration, login, and token management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationException, DuplicateException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)


class AuthService:
    """Encapsulates all authentication business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── User Lookup ──────────────────────────────────────────────
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Find a user by email address."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Find a user by their UUID."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        result = await self.db.execute(
            select(User).where(User.id == uid)
        )
        return result.scalar_one_or_none()

    # ── Registration ─────────────────────────────────────────────
    async def register(self, data: UserRegister) -> AuthResponse:
        """
        Register a new user account.

        Raises:
            DuplicateException: If email is already registered.
        """
        existing = await self.get_user_by_email(data.email)
        if existing:
            raise DuplicateException("User", "email", data.email)

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            role=data.role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        tokens = self._generate_tokens(user)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=tokens,
        )

    # ── Login ────────────────────────────────────────────────────
    async def login(self, data: UserLogin) -> AuthResponse:
        """
        Authenticate a user with email and password.

        Raises:
            AuthenticationException: If credentials are invalid.
        """
        user = await self.get_user_by_email(data.email)
        if not user or not verify_password(data.password, user.password_hash):
            raise AuthenticationException()

        # Update last login timestamp
        user.last_login = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)

        tokens = self._generate_tokens(user)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=tokens,
        )

    # ── Token Refresh ────────────────────────────────────────────
    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Issue new access + refresh tokens from a valid refresh token.

        Raises:
            AuthenticationException: If refresh token is invalid or expired.
        """
        payload = decode_access_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise AuthenticationException("Invalid or expired refresh token")

        user_id = payload.get("sub")
        user = await self.get_user_by_id(user_id) if user_id else None
        if user is None:
            raise AuthenticationException("User not found")

        return self._generate_tokens(user)

    # ── Helpers ──────────────────────────────────────────────────
    @staticmethod
    def _generate_tokens(user: User) -> TokenResponse:
        """Create a fresh pair of access + refresh tokens for the user."""
        token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )
