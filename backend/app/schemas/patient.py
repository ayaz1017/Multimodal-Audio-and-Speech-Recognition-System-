"""
Pydantic schemas for patient endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────
class PatientCreate(BaseModel):
    """POST /patients request body."""
    patient_code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=255)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    diagnosis_notes: Optional[str] = None


class PatientUpdate(BaseModel):
    """PUT /patients/{id} request body. All fields optional."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    diagnosis_notes: Optional[str] = None


# ── Response Schemas ─────────────────────────────────────────────
class PatientResponse(BaseModel):
    """Patient data returned in API responses."""
    id: uuid.UUID
    patient_code: str
    full_name: str
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    diagnosis_notes: Optional[str] = None
    primary_doctor_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientListResponse(BaseModel):
    """Paginated list of patients."""
    patients: List[PatientResponse]
    total: int
    page: int
    page_size: int
