"""
Therapist Patients Routes

Handles patient list, patient detail, invite patients, and manage patient relationships.
"""

from __future__ import annotations

import hashlib
import uuid
import json
from datetime import datetime, timedelta, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import (
    get_current_therapist,
    verify_therapist_patient_access,
    get_patient_by_id,
)


# Router with prefix for all therapist patient endpoints
r = APIRouter(prefix="/api/therapist/patients", tags=["therapist-patients"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _generate_invite_token() -> str:
    """Generate a unique invite token."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:8]


def _get_patient_last_active(db: Session, user_id: int) -> Optional[datetime]:
    """Get the most recent activity timestamp for a patient."""
    # Check multiple tables for last activity
    
    # Last journal entry
    last_journal = (
        db.query(func.max(models.JournalEntries.created_at))
        .join(models.Users, models.Users.user_hash == models.JournalEntries.user_hash)
        .filter(models.Users.id == user_id)
        .scalar()
    )
    
    # Last activity session
    last_activity = (
        db.query(func.max(models.ActivitySessions.created_at))
        .join(models.Users, models.Users.user_hash == models.ActivitySessions.user_hash)
        .filter(models.Users.id == user_id)
        .scalar()
    )
    
    # Last feedback
    last_feedback = (
        db.query(func.max(models.Feedback.created_at))
        .join(models.Sessions, models.Sessions.id == models.Feedback.session_id)
        .join(models.Users, models.Users.user_hash == models.Sessions.user_hash)
        .filter(models.Users.id == user_id)
        .scalar()
    )
    
    # Return the most recent
    timestamps = [t for t in [last_journal, last_activity, last_feedback] if t]
    return max(timestamps) if timestamps else None


def _get_activities_count(db: Session, user_hash: str, days: int = 7) -> int:
    """Get count of activities completed in the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    count = (
        db.query(func.count(models.ActivitySessions.id))
        .filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status == "completed",
            models.ActivitySessions.completed_at >= cutoff,
        )
        .scalar()
    )
    
    return count or 0


def _get_activity_streak(db: Session, user_hash: str, days: int = 7) -> List[bool]:
    """Get activity streak for last N days (list of bools, most recent first)."""
    today = date.today()
    streak = []
    
    for i in range(days):
        check_date = today - timedelta(days=i)
        
        # Check if any activity was completed on this date
        has_activity = (
            db.query(models.ActivitySessions)
            .filter(
                models.ActivitySessions.user_hash == user_hash,
                models.ActivitySessions.status == "completed",
                func.date(models.ActivitySessions.completed_at) == check_date,
            )
            .first()
        ) is not None
        
        streak.append(has_activity)
    
    # Reverse so oldest is first (matches UI expectation)
    return list(reversed(streak))


def _build_patient_summary(
    db: Session,
    patient: models.Users,
    link: models.TherapistPatients,
) -> schemas.PatientSummaryOut:
    """Build a patient summary for list views."""
    last_active = _get_patient_last_active(db, patient.id)
    activities_this_week = _get_activities_count(db, patient.user_hash, days=7)
    activity_streak = _get_activity_streak(db, patient.user_hash, days=7)
    
    return schemas.PatientSummaryOut(
        id=patient.id,
        user_hash=patient.user_hash,
        email=patient.email,
        name=patient.name,
        journey_day=patient.journey_day,
        ba_week=link.ba_week,
        last_session_date=link.last_session_date,
        next_session_date=link.next_session_date,
        status=link.status,
        initial_focus=link.initial_focus,
        last_active=last_active,
        activities_this_week=activities_this_week,
        activity_streak=activity_streak,
    )


# =============================================================================
# LIST PATIENTS
# =============================================================================


@r.get("", response_model=schemas.PatientListOut)
def list_patients(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get list of all patients for the current therapist.
    
    Optional filter by status: active, paused, discharged
    """
    query = (
        db.query(models.TherapistPatients, models.Users)
        .join(models.Users, models.Users.id == models.TherapistPatients.patient_user_id)
        .filter(models.TherapistPatients.therapist_id == current_therapist.id)
    )
    
    if status_filter:
        query = query.filter(models.TherapistPatients.status == status_filter)
    
    # Order by most recently linked
    query = query.order_by(models.TherapistPatients.linked_at.desc())
    
    results = query.all()
    
    patients = []
    for link, patient in results:
        summary = _build_patient_summary(db, patient, link)
        patients.append(summary)
    
    return schemas.PatientListOut(
        patients=patients,
        total=len(patients),
    )


# =============================================================================
# GET PATIENT DETAIL
# =============================================================================


@r.get("/{patient_id}", response_model=schemas.PatientDetailOut)
def get_patient_detail(
    patient_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific patient.
    
    Includes clinical intake data, latest check-in, and activity stats.
    """
    # Verify access
    link = verify_therapist_patient_access(current_therapist, patient_id, db)
    patient = get_patient_by_id(patient_id, db)
    
    # Get last active
    last_active = _get_patient_last_active(db, patient.id)
    
    # Get activity counts
    activities_this_week = _get_activities_count(db, patient.user_hash, days=7)
    activities_last_week = _get_activities_count(db, patient.user_hash, days=14) - activities_this_week
    
    # Get total sessions
    total_sessions = (
        db.query(func.count(models.Sessions.id))
        .filter(models.Sessions.user_hash == patient.user_hash)
        .scalar()
    ) or 0
    
    # Get total journal entries
    total_journal_entries = (
        db.query(func.count(models.JournalEntries.id))
        .filter(models.JournalEntries.user_hash == patient.user_hash)
        .scalar()
    ) or 0
    
    # Get clinical intake
    intake = None
    intake_row = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == patient.user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    if intake_row:
        # Get schema items
        schema_items = (
            db.query(models.SchemaItemResponse)
            .filter(models.SchemaItemResponse.intake_id == intake_row.id)
            .all()
        )
        
        # Get PHQ-9 items
        phq9_items = (
            db.query(models.Phq9ItemResponse)
            .filter(models.Phq9ItemResponse.intake_id == intake_row.id)
            .order_by(models.Phq9ItemResponse.question_number)
            .all()
        )
        
        # Parse week actions
        week_actions = []
        if intake_row.week_actions_json:
            try:
                week_actions = json.loads(intake_row.week_actions_json)
            except (json.JSONDecodeError, TypeError):
                pass
        
        intake = schemas.IntakeFullOut(
            id=intake_row.id,
            user_hash=intake_row.user_hash,
            created_at=intake_row.created_at,
            pre_intake_text=intake_row.pre_intake_text,
            age=intake_row.age,
            postal_code=intake_row.postal_code,
            gender=intake_row.gender,
            in_therapy=intake_row.in_therapy,
            therapy_type=intake_row.therapy_type,
            therapy_duration=intake_row.therapy_duration,
            on_medication=intake_row.on_medication,
            medication_list=intake_row.medication_list,
            medication_duration=intake_row.medication_duration,
            pregnant_or_planning=intake_row.pregnant_or_planning,
            pregnant_notes=intake_row.pregnant_notes,
            psychosis_history=intake_row.psychosis_history,
            psychosis_notes=intake_row.psychosis_notes,
            privacy_ack=intake_row.privacy_ack,
            life_area=intake_row.life_area,
            life_focus=intake_row.life_focus,
            week_actions=week_actions,
            week_plan_text=intake_row.week_plan_text,
            good_life_answer=intake_row.good_life_answer,
            schema_items=[
                schemas.SchemaItemAnswer(
                    schema_key=s.schema_key,
                    prompt=s.prompt,
                    score=s.score,
                    note=s.note,
                )
                for s in schema_items
            ],
            phq9_items=[
                schemas.Phq9ItemAnswer(
                    question_number=p.question_number,
                    prompt=p.prompt,
                    score=p.score,
                    note=p.note,
                )
                for p in phq9_items
            ],
        )
    
    # Get latest mini check-in
    latest_checkin = None
    checkin_row = (
        db.query(models.MiniCheckins)
        .filter(models.MiniCheckins.user_hash == patient.user_hash)
        .order_by(models.MiniCheckins.created_at.desc())
        .first()
    )
    
    if checkin_row:
        latest_checkin = schemas.MiniCheckinOut(
            id=checkin_row.id,
            user_hash=checkin_row.user_hash,
            feeling=checkin_row.feeling,
            body=checkin_row.body,
            energy=checkin_row.energy,
            goal_today=checkin_row.goal_today,
            why_goal=checkin_row.why_goal,
            last_win=checkin_row.last_win,
            hard_thing=checkin_row.hard_thing,
            schema_choice=checkin_row.schema_choice,
            postal_code=checkin_row.postal_code,
            place=checkin_row.place,
            created_at=checkin_row.created_at,
        )
    
    return schemas.PatientDetailOut(
        id=patient.id,
        user_hash=patient.user_hash,
        email=patient.email,
        name=patient.name,
        journey_day=patient.journey_day,
        onboarding_complete=patient.onboarding_complete,
        safety_flag=patient.safety_flag,
        ba_week=link.ba_week,
        ba_start_date=link.ba_start_date,
        last_session_date=link.last_session_date,
        next_session_date=link.next_session_date,
        status=link.status,
        initial_focus=link.initial_focus,
        linked_at=link.linked_at,
        intake=intake,
        latest_checkin=latest_checkin,
        last_active=last_active,
        activities_this_week=activities_this_week,
        activities_last_week=activities_last_week,
        total_sessions=total_sessions,
        total_journal_entries=total_journal_entries,
    )


# =============================================================================
# UPDATE PATIENT LINK (BA week, session dates, status)
# =============================================================================


class PatientLinkUpdateIn(schemas.BaseModel):
    """Schema for updating patient link data."""
    ba_week: Optional[int] = None
    ba_start_date: Optional[date] = None
    last_session_date: Optional[date] = None
    next_session_date: Optional[date] = None
    status: Optional[str] = None
    initial_focus: Optional[str] = None


@r.patch("/{patient_id}", response_model=schemas.PatientDetailOut)
def update_patient_link(
    patient_id: int,
    payload: PatientLinkUpdateIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Update therapist-patient link data.
    
    Used to update BA week, session dates, status, etc.
    """
    # Verify access
    link = verify_therapist_patient_access(current_therapist, patient_id, db)
    
    # Update fields
    if payload.ba_week is not None:
        link.ba_week = payload.ba_week
    
    if payload.ba_start_date is not None:
        link.ba_start_date = payload.ba_start_date
    
    if payload.last_session_date is not None:
        link.last_session_date = payload.last_session_date
    
    if payload.next_session_date is not None:
        link.next_session_date = payload.next_session_date
    
    if payload.status is not None:
        if payload.status not in ["active", "paused", "discharged"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status. Must be: active, paused, or discharged",
            )
        link.status = payload.status
    
    if payload.initial_focus is not None:
        link.initial_focus = payload.initial_focus
    
    db.commit()
    
    # Return updated detail
    return get_patient_detail(patient_id, current_therapist, db)


# =============================================================================
# REMOVE PATIENT (Discharge)
# =============================================================================


@r.delete("/{patient_id}")
def remove_patient(
    patient_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Remove a patient from therapist's list.
    
    This sets status to 'discharged' rather than deleting the link,
    preserving the historical relationship.
    """
    # Verify access
    link = verify_therapist_patient_access(current_therapist, patient_id, db)
    
    # Set status to discharged
    link.status = "discharged"
    db.commit()
    
    return {"ok": True, "message": "Patient discharged successfully"}


# =============================================================================
# LINK EXISTING PATIENT (By Email)
# =============================================================================


class LinkExistingPatientIn(schemas.BaseModel):
    """Schema for linking an existing patient by email."""
    patient_email: str
    initial_focus: Optional[str] = None


@r.post("/link-existing", response_model=schemas.PatientSummaryOut)
def link_existing_patient(
    payload: LinkExistingPatientIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Link an existing patient to this therapist by email.
    
    Use this to connect with patients who already have accounts.
    """
    email = payload.patient_email.lower().strip()
    
    # Find existing user
    patient = (
        db.query(models.Users)
        .filter(models.Users.email == email)
        .first()
    )
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patient found with this email. Use /invite to invite new patients.",
        )
    
    # Check if already linked
    existing_link = (
        db.query(models.TherapistPatients)
        .filter(
            models.TherapistPatients.therapist_id == current_therapist.id,
            models.TherapistPatients.patient_user_id == patient.id,
        )
        .first()
    )
    
    if existing_link:
        if existing_link.status == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This patient is already linked to you",
            )
        else:
            # Reactivate
            existing_link.status = "active"
            existing_link.initial_focus = payload.initial_focus
            db.commit()
            db.refresh(existing_link)
            return _build_patient_summary(db, patient, existing_link)
    
    # Create new link
    new_link = models.TherapistPatients(
        therapist_id=current_therapist.id,
        patient_user_id=patient.id,
        initial_focus=payload.initial_focus,
        status="active",
        ba_week=1,
    )
    db.add(new_link)
    db.commit()
    db.refresh(new_link)
    
    return _build_patient_summary(db, patient, new_link)


# =============================================================================
# INVITE PATIENT
# =============================================================================


@r.post("/invite", response_model=schemas.PatientInviteOut)
def invite_patient(
    payload: schemas.PatientInviteIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Send an invitation to a new patient.
    
    Creates a pending invite that the patient can accept when they sign up.
    """
    email = payload.patient_email.lower().strip()
    
    # Check if patient already exists and is linked
    existing_user = (
        db.query(models.Users)
        .filter(models.Users.email == email)
        .first()
    )
    
    if existing_user:
        # Check if already linked to this therapist
        existing_link = (
            db.query(models.TherapistPatients)
            .filter(
                models.TherapistPatients.therapist_id == current_therapist.id,
                models.TherapistPatients.patient_user_id == existing_user.id,
            )
            .first()
        )
        
        if existing_link:
            if existing_link.status == "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This patient is already linked to you",
                )
            else:
                # Reactivate existing link
                existing_link.status = "active"
                existing_link.initial_focus = payload.initial_focus
                db.commit()
                
                return schemas.PatientInviteOut(
                    id=0,
                    patient_email=email,
                    patient_name=payload.patient_name,
                    initial_focus=payload.initial_focus,
                    invite_token="",
                    status="accepted",
                    expires_at=None,
                    created_at=datetime.utcnow(),
                )
        
        # User exists but not linked - create link directly
        new_link = models.TherapistPatients(
            therapist_id=current_therapist.id,
            patient_user_id=existing_user.id,
            initial_focus=payload.initial_focus,
            status="active",
            ba_week=1,
        )
        db.add(new_link)
        db.commit()
        
        return schemas.PatientInviteOut(
            id=0,
            patient_email=email,
            patient_name=existing_user.name or payload.patient_name,
            initial_focus=payload.initial_focus,
            invite_token="",
            status="accepted",
            expires_at=None,
            created_at=datetime.utcnow(),
        )
    
    # Check for existing pending invite
    existing_invite = (
        db.query(models.PatientInvites)
        .filter(
            models.PatientInvites.therapist_id == current_therapist.id,
            models.PatientInvites.patient_email == email,
            models.PatientInvites.status == "pending",
        )
        .first()
    )
    
    if existing_invite:
        # Update existing invite
        existing_invite.patient_name = payload.patient_name
        existing_invite.initial_focus = payload.initial_focus
        existing_invite.expires_at = datetime.utcnow() + timedelta(days=7)
        db.commit()
        db.refresh(existing_invite)
        
        return schemas.PatientInviteOut(
            id=existing_invite.id,
            patient_email=existing_invite.patient_email,
            patient_name=existing_invite.patient_name,
            initial_focus=existing_invite.initial_focus,
            invite_token=existing_invite.invite_token,
            status=existing_invite.status,
            expires_at=existing_invite.expires_at,
            created_at=existing_invite.created_at,
        )
    
    # Create new invite
    invite_token = _generate_invite_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    invite = models.PatientInvites(
        therapist_id=current_therapist.id,
        patient_email=email,
        patient_name=payload.patient_name,
        initial_focus=payload.initial_focus,
        invite_token=invite_token,
        status="pending",
        expires_at=expires_at,
    )
    
    db.add(invite)
    db.commit()
    db.refresh(invite)
    
    return schemas.PatientInviteOut(
        id=invite.id,
        patient_email=invite.patient_email,
        patient_name=invite.patient_name,
        initial_focus=invite.initial_focus,
        invite_token=invite.invite_token,
        status=invite.status,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
    )


# =============================================================================
# LIST PENDING INVITES
# =============================================================================


@r.get("/invites/pending", response_model=schemas.PatientInviteListOut)
def list_pending_invites(
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get list of pending patient invitations.
    """
    invites = (
        db.query(models.PatientInvites)
        .filter(
            models.PatientInvites.therapist_id == current_therapist.id,
            models.PatientInvites.status == "pending",
        )
        .order_by(models.PatientInvites.created_at.desc())
        .all()
    )
    
    return schemas.PatientInviteListOut(
        invites=[
            schemas.PatientInviteOut(
                id=inv.id,
                patient_email=inv.patient_email,
                patient_name=inv.patient_name,
                initial_focus=inv.initial_focus,
                invite_token=inv.invite_token,
                status=inv.status,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
            )
            for inv in invites
        ]
    )


# =============================================================================
# CANCEL INVITE
# =============================================================================


@r.delete("/invites/{invite_id}")
def cancel_invite(
    invite_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Cancel a pending invitation.
    """
    invite = (
        db.query(models.PatientInvites)
        .filter(
            models.PatientInvites.id == invite_id,
            models.PatientInvites.therapist_id == current_therapist.id,
        )
        .first()
    )
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )
    
    if invite.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel pending invites",
        )
    
    invite.status = "cancelled"
    db.commit()
    
    return {"ok": True, "message": "Invite cancelled"}


# =============================================================================
# ACCEPT INVITE (Called by patient during signup)
# =============================================================================


@r.post("/invites/accept")
def accept_invite(
    invite_token: str = Query(...),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    Accept a patient invitation.
    
    Called when a patient signs up using an invite link.
    This endpoint does NOT require therapist auth - it's called by the patient.
    """
    # Find invite
    invite = (
        db.query(models.PatientInvites)
        .filter(
            models.PatientInvites.invite_token == invite_token,
            models.PatientInvites.status == "pending",
        )
        .first()
    )
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite",
        )
    
    # Check expiration
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        invite.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite has expired",
        )
    
    # Get patient user
    patient = db.query(models.Users).filter(models.Users.id == user_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check if link already exists
    existing_link = (
        db.query(models.TherapistPatients)
        .filter(
            models.TherapistPatients.therapist_id == invite.therapist_id,
            models.TherapistPatients.patient_user_id == patient.id,
        )
        .first()
    )
    
    if existing_link:
        # Reactivate if needed
        existing_link.status = "active"
        existing_link.initial_focus = invite.initial_focus
    else:
        # Create new link
        new_link = models.TherapistPatients(
            therapist_id=invite.therapist_id,
            patient_user_id=patient.id,
            initial_focus=invite.initial_focus,
            status="active",
            ba_week=1,
        )
        db.add(new_link)
    
    # Mark invite as accepted
    invite.status = "accepted"
    invite.accepted_user_id = patient.id
    invite.accepted_at = datetime.utcnow()
    
    db.commit()
    
    return {"ok": True, "message": "Invite accepted successfully"}
