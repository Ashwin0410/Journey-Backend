"""
Therapist Dashboard Routes

Handles dashboard stats, attention needed alerts, and AI-generated patient summaries.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import (
    get_current_therapist,
    verify_therapist_patient_access,
    get_patient_by_id,
)


# Router with prefix for all therapist dashboard endpoints
r = APIRouter(prefix="/api/therapist/dashboard", tags=["therapist-dashboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_patient_last_active(db: Session, user_id: int, user_hash: str) -> Optional[datetime]:
    """Get the most recent activity timestamp for a patient."""
    # Check multiple tables for last activity
    
    # Last journal entry
    last_journal = (
        db.query(func.max(models.JournalEntries.created_at))
        .filter(models.JournalEntries.user_hash == user_hash)
        .scalar()
    )
    
    # Last activity session
    last_activity = (
        db.query(func.max(models.ActivitySessions.created_at))
        .filter(models.ActivitySessions.user_hash == user_hash)
        .scalar()
    )
    
    # Last session (audio journey)
    last_session = (
        db.query(func.max(models.Sessions.created_at))
        .filter(models.Sessions.user_hash == user_hash)
        .scalar()
    )
    
    # Return the most recent
    timestamps = [t for t in [last_journal, last_activity, last_session] if t]
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


def _get_activities_previous_period(db: Session, user_hash: str, days: int = 7) -> int:
    """Get count of activities completed in the previous period (for comparison)."""
    cutoff_end = datetime.utcnow() - timedelta(days=days)
    cutoff_start = cutoff_end - timedelta(days=days)
    
    count = (
        db.query(func.count(models.ActivitySessions.id))
        .filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status == "completed",
            models.ActivitySessions.completed_at >= cutoff_start,
            models.ActivitySessions.completed_at < cutoff_end,
        )
        .scalar()
    )
    
    return count or 0


def _get_latest_phq9_score(db: Session, user_hash: str) -> Optional[int]:
    """Get the total PHQ-9 score from latest intake."""
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    if not intake:
        return None
    
    total = (
        db.query(func.sum(models.Phq9ItemResponse.score))
        .filter(models.Phq9ItemResponse.intake_id == intake.id)
        .scalar()
    )
    
    return total


def _get_latest_journal_quote(db: Session, user_hash: str) -> tuple[Optional[str], Optional[date]]:
    """Get the most recent meaningful journal entry quote."""
    # Look for journal or reflection entries
    entry = (
        db.query(models.JournalEntries)
        .filter(
            models.JournalEntries.user_hash == user_hash,
            models.JournalEntries.entry_type.in_(["journal", "reflection"]),
            models.JournalEntries.body.isnot(None),
            func.length(models.JournalEntries.body) > 20,
        )
        .order_by(models.JournalEntries.created_at.desc())
        .first()
    )
    
    if not entry:
        return None, None
    
    # Truncate if too long
    quote = entry.body
    if len(quote) > 200:
        quote = quote[:197] + "..."
    
    return quote, entry.date


# =============================================================================
# DASHBOARD STATS
# =============================================================================


@r.get("/stats", response_model=schemas.DashboardStatsOut)
def get_dashboard_stats(
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get quick stats for the therapist dashboard.
    
    Returns:
    - Active patients count
    - Total activities this week (across all patients)
    - Patients needing attention count
    - Pending invites count
    """
    # Active patients count
    active_patients = (
        db.query(func.count(models.TherapistPatients.id))
        .filter(
            models.TherapistPatients.therapist_id == current_therapist.id,
            models.TherapistPatients.status == "active",
        )
        .scalar()
    ) or 0
    
    # Get all active patient user_hashes
    patient_links = (
        db.query(models.TherapistPatients, models.Users)
        .join(models.Users, models.Users.id == models.TherapistPatients.patient_user_id)
        .filter(
            models.TherapistPatients.therapist_id == current_therapist.id,
            models.TherapistPatients.status == "active",
        )
        .all()
    )
    
    patient_hashes = [user.user_hash for link, user in patient_links]
    
    # Activities this week (across all patients)
    cutoff = datetime.utcnow() - timedelta(days=7)
    activities_this_week = 0
    
    if patient_hashes:
        activities_this_week = (
            db.query(func.count(models.ActivitySessions.id))
            .filter(
                models.ActivitySessions.user_hash.in_(patient_hashes),
                models.ActivitySessions.status == "completed",
                models.ActivitySessions.completed_at >= cutoff,
            )
            .scalar()
        ) or 0
    
    # Patients needing attention (low activity or high PHQ-9)
    need_attention = 0
    inactive_threshold = datetime.utcnow() - timedelta(days=3)
    
    for link, user in patient_links:
        last_active = _get_patient_last_active(db, user.id, user.user_hash)
        activities = _get_activities_count(db, user.user_hash, days=7)
        prev_activities = _get_activities_previous_period(db, user.user_hash, days=7)
        phq9_score = _get_latest_phq9_score(db, user.user_hash)
        
        # Check for attention needed
        if last_active is None or last_active < inactive_threshold:
            need_attention += 1
        elif activities < prev_activities * 0.5 and prev_activities >= 3:
            # Activity dropped by more than 50%
            need_attention += 1
        elif phq9_score is not None and phq9_score >= 15:
            # Moderately severe or severe depression
            need_attention += 1
    
    # Pending invites count
    pending_invites = (
        db.query(func.count(models.PatientInvites.id))
        .filter(
            models.PatientInvites.therapist_id == current_therapist.id,
            models.PatientInvites.status == "pending",
        )
        .scalar()
    ) or 0
    
    return schemas.DashboardStatsOut(
        active_patients=active_patients,
        activities_this_week=activities_this_week,
        need_attention=need_attention,
        pending_invites=pending_invites,
    )


# =============================================================================
# ATTENTION NEEDED
# =============================================================================


@r.get("/attention", response_model=schemas.AttentionListOut)
def get_attention_needed(
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get list of patients needing attention.
    
    Returns two lists:
    - urgent: Low activity, inactive, high PHQ-9
    - positive: Milestones, achievements
    """
    # Get all active patients
    patient_links = (
        db.query(models.TherapistPatients, models.Users)
        .join(models.Users, models.Users.id == models.TherapistPatients.patient_user_id)
        .filter(
            models.TherapistPatients.therapist_id == current_therapist.id,
            models.TherapistPatients.status == "active",
        )
        .all()
    )
    
    urgent = []
    positive = []
    
    inactive_threshold = datetime.utcnow() - timedelta(days=3)
    
    for link, user in patient_links:
        last_active = _get_patient_last_active(db, user.id, user.user_hash)
        activities_this_week = _get_activities_count(db, user.user_hash, days=7)
        activities_last_week = _get_activities_previous_period(db, user.user_hash, days=7)
        phq9_score = _get_latest_phq9_score(db, user.user_hash)
        
        # Calculate days since last active
        days_inactive = None
        if last_active:
            days_inactive = (datetime.utcnow() - last_active).days
        
        # Check for URGENT conditions
        
        # 1. Inactive for 3+ days
        if last_active is None or last_active < inactive_threshold:
            days_text = f"{days_inactive} days ago" if days_inactive else "Never active"
            
            urgent.append(schemas.AttentionItemOut(
                patient_id=user.id,
                patient_name=user.name,
                patient_email=user.email,
                user_hash=user.user_hash,
                attention_type="inactive",
                attention_badge="Inactive",
                attention_description=f"No activity logged since {days_text}. May need check-in.",
                last_active=last_active,
                last_session_date=link.last_session_date,
                ba_week=link.ba_week,
            ))
            continue  # Don't double-count
        
        # 2. Significant activity drop
        if activities_last_week >= 3 and activities_this_week < activities_last_week * 0.5:
            urgent.append(schemas.AttentionItemOut(
                patient_id=user.id,
                patient_name=user.name,
                patient_email=user.email,
                user_hash=user.user_hash,
                attention_type="low_activity",
                attention_badge="Low Activity",
                attention_description=f"Activity dropped from {activities_last_week} to {activities_this_week} activities. Previously maintaining {activities_last_week} activities. Pattern suggests possible avoidance cycle.",
                last_active=last_active,
                last_session_date=link.last_session_date,
                ba_week=link.ba_week,
            ))
            continue
        
        # 3. High PHQ-9 score
        if phq9_score is not None and phq9_score >= 15:
            severity = "severe" if phq9_score >= 20 else "moderately severe"
            urgent.append(schemas.AttentionItemOut(
                patient_id=user.id,
                patient_name=user.name,
                patient_email=user.email,
                user_hash=user.user_hash,
                attention_type="high_phq9",
                attention_badge="High PHQ-9",
                attention_description=f"PHQ-9 score of {phq9_score} indicates {severity} depression. Clinical review recommended.",
                last_active=last_active,
                last_session_date=link.last_session_date,
                ba_week=link.ba_week,
            ))
            continue
        
        # Check for POSITIVE conditions (milestones)
        
        # 1. First social activity
        social_activities = (
            db.query(models.ActivitySessions)
            .join(models.Activities, models.Activities.id == models.ActivitySessions.activity_id)
            .filter(
                models.ActivitySessions.user_hash == user.user_hash,
                models.ActivitySessions.status == "completed",
                models.Activities.life_area.ilike("%social%"),
            )
            .order_by(models.ActivitySessions.completed_at.desc())
            .limit(2)
            .all()
        )
        
        if len(social_activities) == 1:
            # First social activity ever!
            completed_at = social_activities[0].completed_at
            if completed_at and (datetime.utcnow() - completed_at).days <= 3:
                positive.append(schemas.AttentionItemOut(
                    patient_id=user.id,
                    patient_name=user.name,
                    patient_email=user.email,
                    user_hash=user.user_hash,
                    attention_type="milestone",
                    attention_badge="Milestone",
                    attention_description="Completed first social activity! This is a significant step. High reported mood improvement likely.",
                    last_active=last_active,
                    last_session_date=link.last_session_date,
                    ba_week=link.ba_week,
                    milestone_type="first_social_activity",
                    milestone_description="First social activity completed",
                ))
                continue
        
        # 2. Activity streak (5+ days in a row)
        streak_count = 0
        today = date.today()
        for i in range(7):
            check_date = today - timedelta(days=i)
            has_activity = (
                db.query(models.ActivitySessions)
                .filter(
                    models.ActivitySessions.user_hash == user.user_hash,
                    models.ActivitySessions.status == "completed",
                    func.date(models.ActivitySessions.completed_at) == check_date,
                )
                .first()
            ) is not None
            
            if has_activity:
                streak_count += 1
            else:
                break
        
        if streak_count >= 5:
            positive.append(schemas.AttentionItemOut(
                patient_id=user.id,
                patient_name=user.name,
                patient_email=user.email,
                user_hash=user.user_hash,
                attention_type="milestone",
                attention_badge="Milestone",
                attention_description=f"On a {streak_count}-day activity streak! Consistent engagement showing strong progress.",
                last_active=last_active,
                last_session_date=link.last_session_date,
                ba_week=link.ba_week,
                milestone_type="activity_streak",
                milestone_description=f"{streak_count}-day streak",
            ))
            continue
        
        # 3. Significant activity increase
        if activities_last_week >= 1 and activities_this_week >= activities_last_week * 1.5 and activities_this_week >= 5:
            positive.append(schemas.AttentionItemOut(
                patient_id=user.id,
                patient_name=user.name,
                patient_email=user.email,
                user_hash=user.user_hash,
                attention_type="milestone",
                attention_badge="Milestone",
                attention_description=f"Activity increased from {activities_last_week} to {activities_this_week} this week. Great momentum!",
                last_active=last_active,
                last_session_date=link.last_session_date,
                ba_week=link.ba_week,
                milestone_type="activity_increase",
                milestone_description="50%+ activity increase",
            ))
    
    return schemas.AttentionListOut(
        urgent=urgent,
        positive=positive,
    )


# =============================================================================
# PATIENT AI SUMMARY
# =============================================================================


@r.get("/patients/{patient_id}/summary", response_model=schemas.PatientAISummaryOut)
def get_patient_ai_summary(
    patient_id: int,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get AI-generated summary for a specific patient.
    
    Includes:
    - Weekly summary of activity and engagement
    - What's working well
    - Potential focus areas for next session
    - Recent journal insight
    """
    # Verify access
    link = verify_therapist_patient_access(current_therapist, patient_id, db)
    patient = get_patient_by_id(patient_id, db)
    
    # Gather data for summary
    activities_this_week = _get_activities_count(db, patient.user_hash, days=7)
    activities_last_week = _get_activities_previous_period(db, patient.user_hash, days=7)
    
    # Get activity details for this week
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_activities = (
        db.query(models.ActivitySessions, models.Activities)
        .join(models.Activities, models.Activities.id == models.ActivitySessions.activity_id)
        .filter(
            models.ActivitySessions.user_hash == patient.user_hash,
            models.ActivitySessions.status == "completed",
            models.ActivitySessions.completed_at >= cutoff,
        )
        .order_by(models.ActivitySessions.completed_at.desc())
        .all()
    )
    
    # Get life areas distribution
    life_areas = {}
    for activity_session, activity in recent_activities:
        area = activity.life_area or "Other"
        life_areas[area] = life_areas.get(area, 0) + 1
    
    # Get journal entries
    recent_journals = (
        db.query(models.JournalEntries)
        .filter(
            models.JournalEntries.user_hash == patient.user_hash,
            models.JournalEntries.created_at >= cutoff,
        )
        .order_by(models.JournalEntries.created_at.desc())
        .all()
    )
    
    # Get clinical intake for context
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == patient.user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    # Build weekly summary
    activity_trend = "stable"
    if activities_last_week > 0:
        if activities_this_week > activities_last_week:
            activity_trend = "up"
        elif activities_this_week < activities_last_week:
            activity_trend = "down"
    
    patient_name = patient.name.split()[0] if patient.name else "Patient"
    
    if activity_trend == "up":
        weekly_summary = f"{patient_name} completed {activities_this_week} activities this week, up from {activities_last_week} last week. "
    elif activity_trend == "down":
        weekly_summary = f"{patient_name} completed {activities_this_week} activities this week, down from {activities_last_week} last week. "
    else:
        weekly_summary = f"{patient_name} completed {activities_this_week} activities this week. "
    
    # Add life area insights
    if life_areas:
        top_area = max(life_areas, key=life_areas.get)
        avoided_areas = []
        
        if intake and intake.life_area:
            target_area = intake.life_area
            if target_area not in life_areas or life_areas.get(target_area, 0) == 0:
                avoided_areas.append(target_area)
        
        weekly_summary += f"Most active in {top_area.lower()} activities. "
        
        if avoided_areas:
            weekly_summary += f"No activities logged in {avoided_areas[0].lower()} (their stated focus area)."
    
    # Build "what's working"
    whats_working = ""
    
    # Check for consistent activities
    consistent_types = [area for area, count in life_areas.items() if count >= 3]
    if consistent_types:
        whats_working = f"{consistent_types[0]} activities remain consistent. "
    
    # Check for positive journal sentiment
    positive_journals = [j for j in recent_journals if j.body and any(
        word in j.body.lower() for word in ["better", "good", "helped", "progress", "happy", "proud"]
    )]
    
    if positive_journals:
        whats_working += f"Positive reflections noted in {len(positive_journals)} journal entries. "
    
    if not whats_working:
        whats_working = "Building foundation with initial activities. Engagement with the app shows commitment to the process."
    
    # Build focus areas
    focus_areas = ""
    
    if activity_trend == "down" and activities_last_week > 0:
        drop_pct = int((1 - activities_this_week / activities_last_week) * 100)
        focus_areas = f"Activity dropped {drop_pct}%. Explore what changed this week. "
    
    if avoided_areas:
        focus_areas += f"Avoidance pattern around {avoided_areas[0].lower()} activities. Consider smaller steps in this area. "
    
    # Check for schema patterns
    if intake:
        schema_items = (
            db.query(models.SchemaItemResponse)
            .filter(models.SchemaItemResponse.intake_id == intake.id)
            .order_by(models.SchemaItemResponse.score.desc())
            .limit(2)
            .all()
        )
        
        if schema_items and schema_items[0].score >= 4:
            focus_areas += f"High score on '{schema_items[0].schema_key}' schema - may be influencing avoidance."
    
    if not focus_areas:
        focus_areas = "Maintain current momentum. Consider introducing slightly more challenging activities as confidence builds."
    
    # Get journal insight
    journal_insight, journal_date = _get_latest_journal_quote(db, patient.user_hash)
    
    return schemas.PatientAISummaryOut(
        weekly_summary=weekly_summary.strip(),
        whats_working=whats_working.strip(),
        focus_areas=focus_areas.strip(),
        journal_insight=journal_insight,
        journal_insight_date=journal_date,
        generated_at=datetime.utcnow(),
    )


# =============================================================================
# ACTIVITY HEATMAP
# =============================================================================


@r.get("/patients/{patient_id}/activity-heatmap", response_model=schemas.ActivityHeatmapOut)
def get_activity_heatmap(
    patient_id: int,
    days: int = 14,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Get activity heatmap data for a patient.
    
    Returns activity level for each day in the specified period.
    """
    # Verify access
    link = verify_therapist_patient_access(current_therapist, patient_id, db)
    patient = get_patient_by_id(patient_id, db)
    
    today = date.today()
    period_start = today - timedelta(days=days - 1)
    
    heatmap_days = []
    total_activities = 0
    
    for i in range(days):
        check_date = period_start + timedelta(days=i)
        
        # Count activities on this date
        activity_count = (
            db.query(func.count(models.ActivitySessions.id))
            .filter(
                models.ActivitySessions.user_hash == patient.user_hash,
                models.ActivitySessions.status == "completed",
                func.date(models.ActivitySessions.completed_at) == check_date,
            )
            .scalar()
        ) or 0
        
        total_activities += activity_count
        
        # Determine level (0-3)
        if activity_count == 0:
            level = 0
        elif activity_count == 1:
            level = 1
        elif activity_count == 2:
            level = 2
        else:
            level = 3
        
        heatmap_days.append(schemas.ActivityDayOut(
            date=check_date,
            level=level,
            activity_count=activity_count,
            is_today=(check_date == today),
        ))
    
    return schemas.ActivityHeatmapOut(
        days=heatmap_days,
        total_activities=total_activities,
        period_start=period_start,
        period_end=today,
    )
