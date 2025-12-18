"""
Therapist Notes Routes

Handles CRUD operations for therapist session notes about patients.
"""

from __future__ import annotations

from datetime import datetime, date
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


# Router with prefix for all therapist notes endpoints
r = APIRouter(prefix="/api/therapist/patients", tags=["therapist-notes"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# LIST NOTES FOR A PATIENT
# =============================================================================


@r.get("/{patient_id}/notes", response_model=schemas.TherapistNoteListOut)
def list_patient_notes(
    patient_id: int,
    note_type: Optional[str] = Query(None, description="Filter by note type"),
    limit: int = Query(50, ge=1, le=100, description="Max notes to return"),
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get all notes for a specific patient.
    
    Optional filter by note_type: session_note, follow_up, observation
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    query = (
        db.query(models.TherapistNotes)
        .filter(
            models.TherapistNotes.therapist_id == current_therapist.id,
            models.TherapistNotes.patient_user_id == patient_id,
        )
    )
    
    if note_type:
        query = query.filter(models.TherapistNotes.note_type == note_type)
    
    notes = (
        query
        .order_by(models.TherapistNotes.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return schemas.TherapistNoteListOut(
        notes=[
            schemas.TherapistNoteOut(
                id=note.id,
                therapist_id=note.therapist_id,
                patient_user_id=note.patient_user_id,
                note_text=note.note_text,
                session_date=note.session_date,
                note_type=note.note_type,
                created_at=note.created_at,
                updated_at=note.updated_at,
            )
            for note in notes
        ]
    )


# =============================================================================
# GET SINGLE NOTE
# =============================================================================


@r.get("/{patient_id}/notes/{note_id}", response_model=schemas.TherapistNoteOut)
def get_note(
    patient_id: int,
    note_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get a specific note by ID.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    note = (
        db.query(models.TherapistNotes)
        .filter(
            models.TherapistNotes.id == note_id,
            models.TherapistNotes.therapist_id == current_therapist.id,
            models.TherapistNotes.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    
    return schemas.TherapistNoteOut(
        id=note.id,
        therapist_id=note.therapist_id,
        patient_user_id=note.patient_user_id,
        note_text=note.note_text,
        session_date=note.session_date,
        note_type=note.note_type,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# =============================================================================
# CREATE NOTE
# =============================================================================


@r.post("/{patient_id}/notes", response_model=schemas.TherapistNoteOut)
def create_note(
    patient_id: int,
    payload: schemas.TherapistNoteIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Create a new note for a patient.
    
    Note types:
    - session_note: Notes from a therapy session
    - follow_up: Follow-up observations between sessions
    - observation: General clinical observations
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    # Validate note type
    valid_types = ["session_note", "follow_up", "observation"]
    if payload.note_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid note_type. Must be one of: {', '.join(valid_types)}",
        )
    
    # Create note
    note = models.TherapistNotes(
        therapist_id=current_therapist.id,
        patient_user_id=patient_id,
        note_text=payload.note_text.strip(),
        session_date=payload.session_date,
        note_type=payload.note_type,
    )
    
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return schemas.TherapistNoteOut(
        id=note.id,
        therapist_id=note.therapist_id,
        patient_user_id=note.patient_user_id,
        note_text=note.note_text,
        session_date=note.session_date,
        note_type=note.note_type,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# =============================================================================
# UPDATE NOTE
# =============================================================================


class TherapistNoteUpdateIn(schemas.BaseModel):
    """Schema for updating a note."""
    note_text: Optional[str] = None
    session_date: Optional[date] = None
    note_type: Optional[str] = None


@r.patch("/{patient_id}/notes/{note_id}", response_model=schemas.TherapistNoteOut)
def update_note(
    patient_id: int,
    note_id: int,
    payload: TherapistNoteUpdateIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Update an existing note.
    
    Only updates fields that are provided.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    note = (
        db.query(models.TherapistNotes)
        .filter(
            models.TherapistNotes.id == note_id,
            models.TherapistNotes.therapist_id == current_therapist.id,
            models.TherapistNotes.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    
    # Update fields
    if payload.note_text is not None:
        note.note_text = payload.note_text.strip()
    
    if payload.session_date is not None:
        note.session_date = payload.session_date
    
    if payload.note_type is not None:
        valid_types = ["session_note", "follow_up", "observation"]
        if payload.note_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid note_type. Must be one of: {', '.join(valid_types)}",
            )
        note.note_type = payload.note_type
    
    db.commit()
    db.refresh(note)
    
    return schemas.TherapistNoteOut(
        id=note.id,
        therapist_id=note.therapist_id,
        patient_user_id=note.patient_user_id,
        note_text=note.note_text,
        session_date=note.session_date,
        note_type=note.note_type,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# =============================================================================
# DELETE NOTE
# =============================================================================


@r.delete("/{patient_id}/notes/{note_id}")
def delete_note(
    patient_id: int,
    note_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Delete a note.
    
    This is a hard delete - the note will be permanently removed.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    note = (
        db.query(models.TherapistNotes)
        .filter(
            models.TherapistNotes.id == note_id,
            models.TherapistNotes.therapist_id == current_therapist.id,
            models.TherapistNotes.patient_user_id == patient_id,
        )
        .first()
    )
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    
    db.delete(note)
    db.commit()
    
    return {"ok": True, "message": "Note deleted successfully"}


# =============================================================================
# GET LATEST NOTE (Quick access)
# =============================================================================


@r.get("/{patient_id}/notes/latest", response_model=Optional[schemas.TherapistNoteOut])
def get_latest_note(
    patient_id: int,
    note_type: Optional[str] = Query(None, description="Filter by note type"),
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get the most recent note for a patient.
    
    Useful for showing the last session note in the UI.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    query = (
        db.query(models.TherapistNotes)
        .filter(
            models.TherapistNotes.therapist_id == current_therapist.id,
            models.TherapistNotes.patient_user_id == patient_id,
        )
    )
    
    if note_type:
        query = query.filter(models.TherapistNotes.note_type == note_type)
    
    note = (
        query
        .order_by(models.TherapistNotes.created_at.desc())
        .first()
    )
    
    if not note:
        return None
    
    return schemas.TherapistNoteOut(
        id=note.id,
        therapist_id=note.therapist_id,
        patient_user_id=note.patient_user_id,
        note_text=note.note_text,
        session_date=note.session_date,
        note_type=note.note_type,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# =============================================================================
# AUTO-SAVE NOTE (Upsert by session date)
# =============================================================================


class AutoSaveNoteIn(schemas.BaseModel):
    """Schema for auto-save functionality."""
    note_text: str
    session_date: Optional[date] = None


@r.put("/{patient_id}/notes/autosave", response_model=schemas.TherapistNoteOut)
def autosave_note(
    patient_id: int,
    payload: AutoSaveNoteIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Auto-save a session note.
    
    If a session_note for the given date exists, it will be updated.
    Otherwise, a new note will be created.
    
    This is designed to support auto-save functionality in the UI.
    """
    # Verify access
    verify_therapist_patient_access(current_therapist, patient_id, db)
    
    # Use today if no date provided
    note_date = payload.session_date or date.today()
    
    # Look for existing note for this date
    existing = (
        db.query(models.TherapistNotes)
        .filter(
            models.TherapistNotes.therapist_id == current_therapist.id,
            models.TherapistNotes.patient_user_id == patient_id,
            models.TherapistNotes.note_type == "session_note",
            models.TherapistNotes.session_date == note_date,
        )
        .first()
    )
    
    if existing:
        # Update existing note
        existing.note_text = payload.note_text.strip()
        db.commit()
        db.refresh(existing)
        note = existing
    else:
        # Create new note
        note = models.TherapistNotes(
            therapist_id=current_therapist.id,
            patient_user_id=patient_id,
            note_text=payload.note_text.strip(),
            session_date=note_date,
            note_type="session_note",
        )
        db.add(note)
        db.commit()
        db.refresh(note)
    
    return schemas.TherapistNoteOut(
        id=note.id,
        therapist_id=note.therapist_id,
        patient_user_id=note.patient_user_id,
        note_text=note.note_text,
        session_date=note.session_date,
        note_type=note.note_type,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )
