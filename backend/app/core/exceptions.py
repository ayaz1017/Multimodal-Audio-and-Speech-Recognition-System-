"""
Custom exception classes for structured error handling.
"""

from __future__ import annotations


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    """Resource not found (404)."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} with id '{resource_id}' not found",
            status_code=404,
        )


class DuplicateException(AppException):
    """Duplicate resource conflict (409)."""

    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            message=f"{resource} with {field} '{value}' already exists",
            status_code=409,
        )


class AuthenticationException(AppException):
    """Invalid credentials (401)."""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message=message, status_code=401)


class AuthorizationException(AppException):
    """Insufficient permissions (403)."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message=message, status_code=403)


class AudioProcessingException(AppException):
    """Error during audio processing (422)."""

    def __init__(self, message: str = "Failed to process audio data"):
        super().__init__(message=message, status_code=422)
