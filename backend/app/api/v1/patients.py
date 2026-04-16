"""
Patient routes — full CRUD for patient records.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateException, NotFoundException
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
)
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post(
    "",
    response_model=PatientResponse,
    status_code=201,
    summary="Create a new patient",
)
async def create_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientResponse:
    """
    Register a new patient under the authenticated doctor's care.
    The patient_code must be unique across the system.
    """
    try:
        service = PatientService(db)
        return await service.create_patient(data, current_user.id)
    except DuplicateException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "",
    response_model=PatientListResponse,
    summary="List patients",
)
async def list_patients(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or code"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientListResponse:
    """
    List all patients belonging to the authenticated doctor.
    Supports pagination and optional text search.
    """
    service = PatientService(db)
    return await service.list_patients(
        doctor_id=current_user.id,
        page=page,
        page_size=page_size,
        search=search,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get a single patient",
)
async def get_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientResponse:
    """Retrieve a patient record by ID (must belong to the authenticated doctor)."""
    try:
        service = PatientService(db)
        return await service.get_patient(patient_id, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update a patient",
)
async def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientResponse:
    """Update one or more fields on an existing patient record."""
    try:
        service = PatientService(db)
        return await service.update_patient(patient_id, data, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/{patient_id}",
    status_code=204,
    summary="Delete a patient",
)
async def delete_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete a patient record and all associated sessions.
    This action cannot be undone.
    """
    try:
        service = PatientService(db)
        await service.delete_patient(patient_id, current_user.id)
    except NotFoundException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
