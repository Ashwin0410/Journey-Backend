"""
Therapist AI Guidance Routes

Handles therapist guidance for how the AI companion should interact with each patient.
This guidance shapes the AI's responses to maintain therapeutic consistency between sessions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import (
    get_current_therapist,
    verify_therapist_patient_access,
    get_patient_by_id,
)


# Router with prefix for all therapist guidance endpoints
r = APIRouter(prefix="/api/therapist/patients", tags=["therapist-guidance"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# GET GUIDANCE FOR A PATIENT
# =============================================================================


@r.get("/{patient_id}/guidance", response_model=Optional[schemas.AIGuidanceOut])
def get_guidance(
    patient_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get the current AI guidance for a patient.
    
    Returns the active guidance text that shapes how the AI companion
    responds to this specific patient.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    guidance = (
        db.query(models.TherapistAIGuidance)
        .filter(
            models.TherapistAIGuidance.therapist_id == current_therapist.id,
            models.TherapistAIGuidance.patient_user_id == patient_id,
        )
        .order_by(models.TherapistAIGuidance.created_at.desc())
        .first()
    )
    
    if not guidance:
        return None
    
    return schemas.AIGuidanceOut(
        id=guidance.id,
        therapist_id=guidance.therapist_id,
        patient_user_id=guidance.patient_user_id,
        guidance_text=guidance.guidance_text,
        is_active=guidance.is_active,
        created_at=guidance.created_at,
        updated_at=guidance.updated_at,
    )


# =============================================================================
# CREATE OR UPDATE GUIDANCE
# =============================================================================


@r.post("/{patient_id}/guidance", response_model=schemas.AIGuidanceOut)
def create_or_update_guidance(
    patient_id: int,
    payload: schemas.AIGuidanceIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Create or update AI guidance for a patient.
    
    If guidance already exists for this patient, it will be updated.
    Otherwise, new guidance will be created.
    
    The guidance text shapes how the AI companion responds to this patient.
    It won't override clinical judgment but helps maintain therapeutic
    consistency between sessions.
    
    Example guidance:
    "When Sarah expresses hesitation about social activities, gently explore
    what she's afraid might happen. Use reflective listening. Don't push—
    instead, help her notice the cost of avoidance on her own."
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    # Validate guidance text
    if not payload.guidance_text or not payload.guidance_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guidance text cannot be empty",
        )
    
    # Check for existing guidance
    existing = (
        db.query(models.TherapistAIGuidance)
        .filter(
            models.TherapistAIGuidance.therapist_id == current_therapist.id,
            models.TherapistAIGuidance.patient_user_id == patient_id,
        )
        .first()
    )
    
    if existing:
        # Update existing guidance
        existing.guidance_text = payload.guidance_text.strip()
        existing.is_active = payload.is_active
        db.commit()
        db.refresh(existing)
        guidance = existing
    else:
        # Create new guidance
        guidance = models.TherapistAIGuidance(
            therapist_id=current_therapist.id,
            patient_user_id=patient_id,
            guidance_text=payload.guidance_text.strip(),
            is_active=payload.is_active,
        )
        db.add(guidance)
        db.commit()
        db.refresh(guidance)
    
    return schemas.AIGuidanceOut(
        id=guidance.id,
        therapist_id=guidance.therapist_id,
        patient_user_id=guidance.patient_user_id,
        guidance_text=guidance.guidance_text,
        is_active=guidance.is_active,
        created_at=guidance.created_at,
        updated_at=guidance.updated_at,
    )


# =============================================================================
# UPDATE GUIDANCE (PATCH)
# =============================================================================


class AIGuidanceUpdateIn(schemas.BaseModel):
    """Schema for partial guidance update."""
    guidance_text: Optional[str] = None
    is_active: Optional[bool] = None


@r.patch("/{patient_id}/guidance", response_model=schemas.AIGuidanceOut)
def update_guidance(
    patient_id: int,
    payload: AIGuidanceUpdateIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Partially update AI guidance for a patient.
    
    Only updates fields that are provided.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    guidance = (
        db.query(models.TherapistAIGuidance)
        .filter(
            models.TherapistAIGuidance.therapist_id == current_therapist.id,
            models.TherapistAIGuidance.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not guidance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No guidance found for this patient. Use POST to create guidance first.",
        )
    
    # Update fields
    if payload.guidance_text is not None:
        if not payload.guidance_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guidance text cannot be empty",
            )
        guidance.guidance_text = payload.guidance_text.strip()
    
    if payload.is_active is not None:
        guidance.is_active = payload.is_active
    
    db.commit()
    db.refresh(guidance)
    
    return schemas.AIGuidanceOut(
        id=guidance.id,
        therapist_id=guidance.therapist_id,
        patient_user_id=guidance.patient_user_id,
        guidance_text=guidance.guidance_text,
        is_active=guidance.is_active,
        created_at=guidance.created_at,
        updated_at=guidance.updated_at,
    )


# =============================================================================
# DELETE GUIDANCE
# =============================================================================


@r.delete("/{patient_id}/guidance")
def delete_guidance(
    patient_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Delete AI guidance for a patient.
    
    This removes the custom guidance, and the AI will use default behavior.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    guidance = (
        db.query(models.TherapistAIGuidance)
        .filter(
            models.TherapistAIGuidance.therapist_id == current_therapist.id,
            models.TherapistAIGuidance.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not guidance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No guidance found for this patient",
        )
    
    db.delete(guidance)
    db.commit()
    
    return {"ok": True, "message": "Guidance deleted successfully"}


# =============================================================================
# TOGGLE GUIDANCE ACTIVE STATE
# =============================================================================


@r.post("/{patient_id}/guidance/toggle", response_model=schemas.AIGuidanceOut)
def toggle_guidance(
    patient_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Toggle the active state of guidance.
    
    If active, guidance will be deactivated.
    If inactive, guidance will be activated.
    
    This allows temporarily disabling guidance without deleting it.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    guidance = (
        db.query(models.TherapistAIGuidance)
        .filter(
            models.TherapistAIGuidance.therapist_id == current_therapist.id,
            models.TherapistAIGuidance.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not guidance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No guidance found for this patient",
        )
    
    # Toggle
    guidance.is_active = not guidance.is_active
    db.commit()
    db.refresh(guidance)
    
    return schemas.AIGuidanceOut(
        id=guidance.id,
        therapist_id=guidance.therapist_id,
        patient_user_id=guidance.patient_user_id,
        guidance_text=guidance.guidance_text,
        is_active=guidance.is_active,
        created_at=guidance.created_at,
        updated_at=guidance.updated_at,
    )


# =============================================================================
# GET GUIDANCE FOR AI (Internal use - no auth required from therapist)
# =============================================================================


@r.get("/by-user-hash/{user_hash}/guidance/active", response_model=Optional[schemas.AIGuidanceOut])
def get_active_guidance_for_user(
    user_hash: str,
    db: Session = Depends(get_db),
):
    """
    Get active AI guidance for a patient by user_hash.
    
    This endpoint is designed for internal use by the AI system to fetch
    the therapist's guidance when generating responses for a patient.
    
    Note: This endpoint does not require therapist authentication as it's
    called by the AI system, not the therapist directly.
    """
    # Find the patient
    patient = (
        db.query(models.Users)
        .filter(models.Users.user_hash == user_hash)
        .first()
    )
    
    if not patient:
        return None
    
    # Find active guidance for this patient
    guidance = (
        db.query(models.TherapistAIGuidance)
        .filter(
            models.TherapistAIGuidance.patient_user_id == patient.id,
            models.TherapistAIGuidance.is_active == True,
        )
        .order_by(models.TherapistAIGuidance.updated_at.desc())
        .first()
    )
    
    if not guidance:
        return None
    
    return schemas.AIGuidanceOut(
        id=guidance.id,
        therapist_id=guidance.therapist_id,
        patient_user_id=guidance.patient_user_id,
        guidance_text=guidance.guidance_text,
        is_active=guidance.is_active,
        created_at=guidance.created_at,
        updated_at=guidance.updated_at,
    )
