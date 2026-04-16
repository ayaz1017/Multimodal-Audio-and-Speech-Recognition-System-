"""
Authentication routes — register, login, and token refresh.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationException, DuplicateException
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    TokenRefresh,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    summary="Register a new user account",
)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Create a new doctor or admin account.

    Returns the created user and a pair of JWT tokens.
    """
    try:
        service = AuthService(db)
        return await service.register(data)
    except DuplicateException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate with email and password.

    Returns the user profile and a pair of JWT tokens.
    """
    try:
        service = AuthService(db)
        return await service.login(data)
    except AuthenticationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    """
    try:
        service = AuthService(db)
        return await service.refresh_tokens(data.refresh_token)
    except AuthenticationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
