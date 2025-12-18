"""
Therapist Activities Routes

Handles therapist-suggested activities for patients.
Therapists can curate a list of activities for each patient,
which appear in the patient's activity recommendations.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import (
    get_current_therapist,
    verify_therapist_patient_access,
    get_patient_by_id,
)


# Router with prefix for all therapist activities endpoints
r = APIRouter(prefix="/api/therapist/patients", tags=["therapist-activities"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# LIST SUGGESTED ACTIVITIES FOR A PATIENT
# =============================================================================


@r.get("/{patient_id}/suggested-activities", response_model=schemas.SuggestedActivityListOut)
def list_suggested_activities(
    patient_id: int,
    include_disabled: bool = Query(False, description="Include disabled activities"),
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get all therapist-suggested activities for a patient.
    
    By default, only returns enabled activities.
    Set include_disabled=true to see all activities.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    query = (
        db.query(models.TherapistSuggestedActivities)
        .filter(
            models.TherapistSuggestedActivities.therapist_id == current_therapist.id,
            models.TherapistSuggestedActivities.patient_user_id == patient_id,
        )
    )
    
    if not include_disabled:
        query = query.filter(models.TherapistSuggestedActivities.is_enabled == True)
    
    activities = (
        query
        .order_by(models.TherapistSuggestedActivities.created_at.desc())
        .all()
    )
    
    return schemas.SuggestedActivityListOut(
        activities=[
            schemas.SuggestedActivityOut(
                id=act.id,
                therapist_id=act.therapist_id,
                patient_user_id=act.patient_user_id,
                title=act.title,
                description=act.description,
                category=act.category,
                duration_minutes=act.duration_minutes,
                barrier_level=act.barrier_level,
                source_note=act.source_note,
                is_enabled=act.is_enabled,
                created_at=act.created_at,
                updated_at=act.updated_at,
            )
            for act in activities
        ]
    )


# =============================================================================
# GET SINGLE SUGGESTED ACTIVITY
# =============================================================================


@r.get("/{patient_id}/suggested-activities/{activity_id}", response_model=schemas.SuggestedActivityOut)
def get_suggested_activity(
    patient_id: int,
    activity_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get a specific suggested activity by ID.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    activity = (
        db.query(models.TherapistSuggestedActivities)
        .filter(
            models.TherapistSuggestedActivities.id == activity_id,
            models.TherapistSuggestedActivities.therapist_id == current_therapist.id,
            models.TherapistSuggestedActivities.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggested activity not found",
        )
    
    return schemas.SuggestedActivityOut(
        id=activity.id,
        therapist_id=activity.therapist_id,
        patient_user_id=activity.patient_user_id,
        title=activity.title,
        description=activity.description,
        category=activity.category,
        duration_minutes=activity.duration_minutes,
        barrier_level=activity.barrier_level,
        source_note=activity.source_note,
        is_enabled=activity.is_enabled,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


# =============================================================================
# CREATE SUGGESTED ACTIVITY
# =============================================================================


@r.post("/{patient_id}/suggested-activities", response_model=schemas.SuggestedActivityOut)
def create_suggested_activity(
    patient_id: int,
    payload: schemas.SuggestedActivityIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Create a new suggested activity for a patient.
    
    Categories:
    - Connection: Social activities
    - Mastery: Skill-building, accomplishment
    - Physical: Exercise, movement
    - Enjoyment: Pleasant activities
    - Self-care: Rest, wellness
    
    Barrier levels:
    - Low: Easy to do, minimal effort
    - Medium: Some effort required
    - High: Challenging, significant effort
    
    Source note: Where this suggestion came from
    - e.g., "From her values", "Grounding technique", "Discussed in session"
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    # Validate title
    if not payload.title or not payload.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activity title cannot be empty",
        )
    
    # Validate category
    valid_categories = ["Connection", "Mastery", "Physical", "Enjoyment", "Self-care"]
    if payload.category and payload.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}",
        )
    
    # Validate barrier level
    valid_barriers = ["Low", "Medium", "High"]
    if payload.barrier_level and payload.barrier_level not in valid_barriers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid barrier_level. Must be one of: {', '.join(valid_barriers)}",
        )
    
    # Create activity
    activity = models.TherapistSuggestedActivities(
        therapist_id=current_therapist.id,
        patient_user_id=patient_id,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        category=payload.category,
        duration_minutes=payload.duration_minutes,
        barrier_level=payload.barrier_level,
        source_note=payload.source_note.strip() if payload.source_note else None,
        is_enabled=payload.is_enabled,
    )
    
    db.add(activity)
    db.commit()
    db.refresh(activity)
    
    return schemas.SuggestedActivityOut(
        id=activity.id,
        therapist_id=activity.therapist_id,
        patient_user_id=activity.patient_user_id,
        title=activity.title,
        description=activity.description,
        category=activity.category,
        duration_minutes=activity.duration_minutes,
        barrier_level=activity.barrier_level,
        source_note=activity.source_note,
        is_enabled=activity.is_enabled,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


# =============================================================================
# UPDATE SUGGESTED ACTIVITY
# =============================================================================


class SuggestedActivityUpdateIn(schemas.BaseModel):
    """Schema for updating a suggested activity."""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    duration_minutes: Optional[int] = None
    barrier_level: Optional[str] = None
    source_note: Optional[str] = None
    is_enabled: Optional[bool] = None


@r.patch("/{patient_id}/suggested-activities/{activity_id}", response_model=schemas.SuggestedActivityOut)
def update_suggested_activity(
    patient_id: int,
    activity_id: int,
    payload: SuggestedActivityUpdateIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Update a suggested activity.
    
    Only updates fields that are provided.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    activity = (
        db.query(models.TherapistSuggestedActivities)
        .filter(
            models.TherapistSuggestedActivities.id == activity_id,
            models.TherapistSuggestedActivities.therapist_id == current_therapist.id,
            models.TherapistSuggestedActivities.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggested activity not found",
        )
    
    # Update fields
    if payload.title is not None:
        if not payload.title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity title cannot be empty",
            )
        activity.title = payload.title.strip()
    
    if payload.description is not None:
        activity.description = payload.description.strip() if payload.description else None
    
    if payload.category is not None:
        valid_categories = ["Connection", "Mastery", "Physical", "Enjoyment", "Self-care"]
        if payload.category and payload.category not in valid_categories:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}",
            )
        activity.category = payload.category
    
    if payload.duration_minutes is not None:
        activity.duration_minutes = payload.duration_minutes
    
    if payload.barrier_level is not None:
        valid_barriers = ["Low", "Medium", "High"]
        if payload.barrier_level and payload.barrier_level not in valid_barriers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid barrier_level. Must be one of: {', '.join(valid_barriers)}",
            )
        activity.barrier_level = payload.barrier_level
    
    if payload.source_note is not None:
        activity.source_note = payload.source_note.strip() if payload.source_note else None
    
    if payload.is_enabled is not None:
        activity.is_enabled = payload.is_enabled
    
    db.commit()
    db.refresh(activity)
    
    return schemas.SuggestedActivityOut(
        id=activity.id,
        therapist_id=activity.therapist_id,
        patient_user_id=activity.patient_user_id,
        title=activity.title,
        description=activity.description,
        category=activity.category,
        duration_minutes=activity.duration_minutes,
        barrier_level=activity.barrier_level,
        source_note=activity.source_note,
        is_enabled=activity.is_enabled,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


# =============================================================================
# DELETE SUGGESTED ACTIVITY
# =============================================================================


@r.delete("/{patient_id}/suggested-activities/{activity_id}")
def delete_suggested_activity(
    patient_id: int,
    activity_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Delete a suggested activity.
    
    This permanently removes the activity from the patient's suggestions.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    activity = (
        db.query(models.TherapistSuggestedActivities)
        .filter(
            models.TherapistSuggestedActivities.id == activity_id,
            models.TherapistSuggestedActivities.therapist_id == current_therapist.id,
            models.TherapistSuggestedActivities.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggested activity not found",
        )
    
    db.delete(activity)
    db.commit()
    
    return {"ok": True, "message": "Activity deleted successfully"}


# =============================================================================
# TOGGLE ACTIVITY ENABLED STATE
# =============================================================================


@r.post("/{patient_id}/suggested-activities/{activity_id}/toggle", response_model=schemas.SuggestedActivityOut)
def toggle_activity(
    patient_id: int,
    activity_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Toggle the enabled state of a suggested activity.
    
    Disabled activities won't appear in the patient's recommendations
    but are preserved for future use.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    activity = (
        db.query(models.TherapistSuggestedActivities)
        .filter(
            models.TherapistSuggestedActivities.id == activity_id,
            models.TherapistSuggestedActivities.therapist_id == current_therapist.id,
            models.TherapistSuggestedActivities.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggested activity not found",
        )
    
    # Toggle
    activity.is_enabled = not activity.is_enabled
    db.commit()
    db.refresh(activity)
    
    return schemas.SuggestedActivityOut(
        id=activity.id,
        therapist_id=activity.therapist_id,
        patient_user_id=activity.patient_user_id,
        title=activity.title,
        description=activity.description,
        category=activity.category,
        duration_minutes=activity.duration_minutes,
        barrier_level=activity.barrier_level,
        source_note=activity.source_note,
        is_enabled=activity.is_enabled,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


# =============================================================================
# BULK CREATE ACTIVITIES (Quick setup)
# =============================================================================


class BulkActivityIn(schemas.BaseModel):
    """Schema for bulk activity creation."""
    activities: List[schemas.SuggestedActivityIn]


class BulkActivityOut(schemas.BaseModel):
    """Schema for bulk activity response."""
    created: int
    activities: List[schemas.SuggestedActivityOut]


@r.post("/{patient_id}/suggested-activities/bulk", response_model=BulkActivityOut)
def bulk_create_activities(
    patient_id: int,
    payload: BulkActivityIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Create multiple suggested activities at once.
    
    Useful for quickly setting up a patient's activity list.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    if not payload.activities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No activities provided",
        )
    
    if len(payload.activities) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 20 activities per bulk create",
        )
    
    created_activities = []
    
    for act_in in payload.activities:
        if not act_in.title or not act_in.title.strip():
            continue  # Skip empty titles
        
        activity = models.TherapistSuggestedActivities(
            therapist_id=current_therapist.id,
            patient_user_id=patient_id,
            title=act_in.title.strip(),
            description=act_in.description.strip() if act_in.description else None,
            category=act_in.category,
            duration_minutes=act_in.duration_minutes,
            barrier_level=act_in.barrier_level,
            source_note=act_in.source_note.strip() if act_in.source_note else None,
            is_enabled=act_in.is_enabled,
        )
        db.add(activity)
        created_activities.append(activity)
    
    db.commit()
    
    # Refresh all to get IDs
    for act in created_activities:
        db.refresh(act)
    
    return BulkActivityOut(
        created=len(created_activities),
        activities=[
            schemas.SuggestedActivityOut(
                id=act.id,
                therapist_id=act.therapist_id,
                patient_user_id=act.patient_user_id,
                title=act.title,
                description=act.description,
                category=act.category,
                duration_minutes=act.duration_minutes,
                barrier_level=act.barrier_level,
                source_note=act.source_note,
                is_enabled=act.is_enabled,
                created_at=act.created_at,
                updated_at=act.updated_at,
            )
            for act in created_activities
        ],
    )


# =============================================================================
# GET SUGGESTED ACTIVITIES FOR PATIENT (Internal - by user_hash)
# =============================================================================


@r.get("/by-user-hash/{user_hash}/suggested-activities/enabled", response_model=schemas.SuggestedActivityListOut)
def get_enabled_activities_for_user(
    user_hash: str,
    db: Session = Depends(get_db),
):
    """
    Get enabled suggested activities for a patient by user_hash.
    
    This endpoint is designed for internal use by the patient app
    to display therapist-suggested activities.
    
    Note: This endpoint does not require therapist authentication.
    """
    # Find the patient
    patient = (
        db.query(models.Users)
        .filter(models.Users.user_hash == user_hash)
        .first()
    )
    
    if not patient:
        return schemas.SuggestedActivityListOut(activities=[])
    
    # Find enabled activities for this patient
    activities = (
        db.query(models.TherapistSuggestedActivities)
        .filter(
            models.TherapistSuggestedActivities.patient_user_id == patient.id,
            models.TherapistSuggestedActivities.is_enabled == True,
        )
        .order_by(models.TherapistSuggestedActivities.created_at.desc())
        .all()
    )
    
    return schemas.SuggestedActivityListOut(
        activities=[
            schemas.SuggestedActivityOut(
                id=act.id,
                therapist_id=act.therapist_id,
                patient_user_id=act.patient_user_id,
                title=act.title,
                description=act.description,
                category=act.category,
                duration_minutes=act.duration_minutes,
                barrier_level=act.barrier_level,
                source_note=act.source_note,
                is_enabled=act.is_enabled,
                created_at=act.created_at,
                updated_at=act.updated_at,
            )
            for act in activities
        ]
    )
