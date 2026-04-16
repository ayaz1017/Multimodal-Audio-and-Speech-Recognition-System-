"""
Patient service — CRUD operations for patient records.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateException, NotFoundException
from app.models.patient import Patient
from app.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
)


class PatientService:
    """Encapsulates all patient management business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ───────────────────────────────────────────────────
    async def create_patient(
        self, data: PatientCreate, doctor_id: uuid.UUID
    ) -> PatientResponse:
        """
        Create a new patient record linked to the given doctor.

        Raises:
            DuplicateException: If patient_code already exists.
        """
        existing = await self._get_by_code(data.patient_code)
        if existing:
            raise DuplicateException("Patient", "patient_code", data.patient_code)

        patient = Patient(
            patient_code=data.patient_code,
            full_name=data.full_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            diagnosis_notes=data.diagnosis_notes,
            primary_doctor_id=doctor_id,
        )
        self.db.add(patient)
        await self.db.commit()
        await self.db.refresh(patient)
        return PatientResponse.model_validate(patient)

    # ── Read (single) ────────────────────────────────────────────
    async def get_patient(
        self, patient_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> PatientResponse:
        """
        Retrieve a single patient by ID. Only returns patients belonging
        to the requesting doctor.

        Raises:
            NotFoundException: If patient doesn't exist or belongs to another doctor.
        """
        patient = await self._get_owned_patient(patient_id, doctor_id)
        return PatientResponse.model_validate(patient)

    # ── Read (list) ──────────────────────────────────────────────
    async def list_patients(
        self,
        doctor_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
    ) -> PatientListResponse:
        """
        List patients belonging to the given doctor with optional search
        and pagination.
        """
        query = select(Patient).where(Patient.primary_doctor_id == doctor_id)

        # Optional full-text search on name or code
        if search:
            search_filter = f"%{search}%"
            query = query.where(
                Patient.full_name.ilike(search_filter)
                | Patient.patient_code.ilike(search_filter)
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = (
            query.order_by(Patient.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        patients = result.scalars().all()

        return PatientListResponse(
            patients=[PatientResponse.model_validate(p) for p in patients],
            total=total,
            page=page,
            page_size=page_size,
        )

    # ── Update ───────────────────────────────────────────────────
    async def update_patient(
        self,
        patient_id: uuid.UUID,
        data: PatientUpdate,
        doctor_id: uuid.UUID,
    ) -> PatientResponse:
        """
        Update fields on an existing patient.

        Raises:
            NotFoundException: If patient doesn't exist or belongs to another doctor.
        """
        patient = await self._get_owned_patient(patient_id, doctor_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(patient, field, value)

        await self.db.commit()
        await self.db.refresh(patient)
        return PatientResponse.model_validate(patient)

    # ── Delete ───────────────────────────────────────────────────
    async def delete_patient(
        self, patient_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> None:
        """
        Delete a patient record.

        Raises:
            NotFoundException: If patient doesn't exist or belongs to another doctor.
        """
        patient = await self._get_owned_patient(patient_id, doctor_id)
        await self.db.delete(patient)
        await self.db.commit()

    # ── Internal Helpers ─────────────────────────────────────────
    async def _get_by_code(self, code: str) -> Optional[Patient]:
        result = await self.db.execute(
            select(Patient).where(Patient.patient_code == code)
        )
        return result.scalar_one_or_none()

    async def _get_owned_patient(
        self, patient_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> Patient:
        """Fetch a patient, ensuring it belongs to the requesting doctor."""
        result = await self.db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.primary_doctor_id == doctor_id,
            )
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise NotFoundException("Patient", str(patient_id))
        return patient
