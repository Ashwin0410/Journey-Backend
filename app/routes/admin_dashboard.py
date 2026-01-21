# routes/admin_dashboard.py
# CHANGE #10: Admin Console Dashboard Routes (No Auth Required)
# UPDATED: Complete user data visibility + CSV export functionality
"""
Admin dashboard endpoints for the ReWire Admin Console.
Provides statistics, user management, and data viewing capabilities.
NO AUTHENTICATION - Direct access for simplicity.

UPDATES:
- Expanded user detail to show ALL data (ML questionnaire, chills, videos, etc.)
- Added CSV export endpoints for all data types
- Removed limits on data retrieval for complete visibility
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import csv
import io
import json

from ..auth_utils import get_db
from .. import models


r = APIRouter(prefix="/api/admin", tags=["admin-dashboard"])


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================


class DashboardStats(BaseModel):
    total_users: int
    active_users_today: int
    active_users_week: int
    total_sessions: int
    sessions_today: int
    total_activities_completed: int
    activities_today: int
    total_journal_entries: int
    avg_sessions_per_user: float
    total_feedback: int
    total_chills: int
    total_video_sessions: int
    total_ml_questionnaires: int


class UserSummary(BaseModel):
    id: int
    user_hash: str
    name: Optional[str] = None
    email: Optional[str] = None
    journey_day: int
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    total_sessions: int
    total_activities: int


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# DASHBOARD STATS
# =============================================================================


@r.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
):
    """
    Get dashboard statistics overview.
    Only counts active (non-deleted) users.
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    
    # ==========================================================================
    # SOFT DELETE: Only count active (non-deleted) users
    # ==========================================================================
    total_users = (
        db.query(func.count(models.Users.id))
        .filter(models.Users.deleted_at.is_(None))
        .scalar() or 0
    )
    
    # Active users today (users with sessions today)
    active_today_sessions = (
        db.query(func.count(func.distinct(models.Sessions.user_hash)))
        .filter(models.Sessions.created_at >= today_start)
        .scalar() or 0
    )
    
    # Active users this week
    active_week_sessions = (
        db.query(func.count(func.distinct(models.Sessions.user_hash)))
        .filter(models.Sessions.created_at >= week_ago)
        .scalar() or 0
    )
    
    # Total sessions
    total_sessions = db.query(func.count(models.Sessions.id)).scalar() or 0
    
    # Sessions today
    sessions_today = (
        db.query(func.count(models.Sessions.id))
        .filter(models.Sessions.created_at >= today_start)
        .scalar() or 0
    )
    
    # Total activities completed
    total_activities = (
        db.query(func.count(models.ActivitySessions.id))
        .filter(models.ActivitySessions.completed_at.isnot(None))
        .scalar() or 0
    )
    
    # Activities completed today
    activities_today = (
        db.query(func.count(models.ActivitySessions.id))
        .filter(
            models.ActivitySessions.completed_at.isnot(None),
            models.ActivitySessions.completed_at >= today_start,
        )
        .scalar() or 0
    )
    
    # Total journal entries
    total_journal = db.query(func.count(models.JournalEntries.id)).scalar() or 0
    
    # Average sessions per user
    avg_sessions = 0.0
    if total_users > 0:
        avg_sessions = round(total_sessions / total_users, 2)
    
    # Total feedback entries
    total_feedback = db.query(func.count(models.Feedback.id)).scalar() or 0
    
    # Total chills timestamps
    total_chills = 0
    try:
        total_chills = db.query(func.count(models.ChillsTimestamp.id)).scalar() or 0
    except Exception:
        pass
    
    # Total video sessions
    total_video_sessions = 0
    try:
        total_video_sessions = db.query(func.count(models.VideoSession.id)).scalar() or 0
    except Exception:
        pass
    
    # Total ML questionnaires completed
    total_ml_questionnaires = 0
    try:
        total_ml_questionnaires = db.query(func.count(models.MLQuestionnaireResponse.id)).scalar() or 0
    except Exception:
        pass
    
    return {
        "total_users": total_users,
        "active_users_today": active_today_sessions,
        "active_users_week": active_week_sessions,
        "total_sessions": total_sessions,
        "sessions_today": sessions_today,
        "total_activities_completed": total_activities,
        "activities_today": activities_today,
        "total_journal_entries": total_journal,
        "avg_sessions_per_user": avg_sessions,
        "total_feedback": total_feedback,
        "total_chills": total_chills,
        "total_video_sessions": total_video_sessions,
        "total_ml_questionnaires": total_ml_questionnaires,
    }


# =============================================================================
# USER MANAGEMENT
# =============================================================================


@r.get("/users")
def list_users(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    include_deleted: bool = Query(False),
):
    """
    List all users with pagination and search.
    By default, excludes deleted users (deleted_at is not null).
    Set include_deleted=true to see all users including deleted ones.
    """
    query = db.query(models.Users)
    
    # ==========================================================================
    # SOFT DELETE: Filter out deleted users by default
    # ==========================================================================
    if not include_deleted:
        query = query.filter(models.Users.deleted_at.is_(None))
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.Users.name.ilike(search_term)) |
            (models.Users.email.ilike(search_term)) |
            (models.Users.user_hash.ilike(search_term))
        )
    
    # Get total count
    total = query.count()
    
    # Sort
    if sort_order == "desc":
        query = query.order_by(desc(models.Users.created_at))
    else:
        query = query.order_by(models.Users.created_at)
    
    # Paginate
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()
    
    # Build response with additional stats
    items = []
    for user in users:
        # Count sessions for this user
        session_count = (
            db.query(func.count(models.Sessions.id))
            .filter(models.Sessions.user_hash == user.user_hash)
            .scalar() or 0
        )
        
        # Count completed activities
        activity_count = (
            db.query(func.count(models.ActivitySessions.id))
            .filter(
                models.ActivitySessions.user_hash == user.user_hash,
                models.ActivitySessions.completed_at.isnot(None),
            )
            .scalar() or 0
        )
        
        # Count chills
        chills_count = 0
        try:
            chills_count = (
                db.query(func.count(models.ChillsTimestamp.id))
                .filter(models.ChillsTimestamp.user_hash == user.user_hash)
                .scalar() or 0
            )
        except Exception:
            pass
        
        # Get last session
        last_session = (
            db.query(models.Sessions.created_at)
            .filter(models.Sessions.user_hash == user.user_hash)
            .order_by(desc(models.Sessions.created_at))
            .first()
        )
        
        items.append({
            "id": user.id,
            "user_hash": user.user_hash,
            "name": user.name,
            "email": user.email,
            "journey_day": user.journey_day or 1,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_active": last_session[0].isoformat() if last_session and last_session[0] else None,
            "total_sessions": session_count,
            "total_activities": activity_count,
            "total_chills": chills_count,
            "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        })
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@r.get("/users/{user_id}")
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Get COMPLETE detailed information for a specific user.
    Returns ALL data including:
    - Basic user info
    - Full intake data (demographics, safety questions)
    - PHQ-9 scores
    - Schema scores
    - ML Questionnaire answers (9 personality questions)
    - Video suggestions (ML recommendations)
    - Video sessions (watching history)
    - Chills timestamps (every chills button press)
    - Body map spots (where they felt chills)
    - Post-video responses (insights, values, actions)
    - ALL sessions (no limit)
    - ALL activities (no limit)
    - ALL journal entries (full body text)
    - ALL feedback
    - Mini check-ins
    """
    user = db.query(models.Users).filter(models.Users.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user_hash = user.user_hash
    
    # =========================================================================
    # FULL INTAKE DATA (All fields)
    # =========================================================================
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .first()
    )
    
    intake_data = None
    if intake:
        intake_data = {
            "id": intake.id,
            "pre_intake_text": intake.pre_intake_text,
            "age": intake.age,
            "gender": intake.gender,
            "postal_code": intake.postal_code,
            "in_therapy": intake.in_therapy,
            "therapy_type": intake.therapy_type,
            "therapy_duration": intake.therapy_duration,
            "on_medication": intake.on_medication,
            "medication_list": intake.medication_list,
            "medication_duration": intake.medication_duration,
            "pregnant_or_planning": intake.pregnant_or_planning,
            "pregnant_notes": intake.pregnant_notes,
            "psychosis_history": intake.psychosis_history,
            "psychosis_notes": intake.psychosis_notes,
            "privacy_ack": intake.privacy_ack,
            "life_area": intake.life_area,
            "life_focus": intake.life_focus,
            "week_actions_json": intake.week_actions_json,
            "week_plan_text": intake.week_plan_text,
            "good_life_answer": intake.good_life_answer,
            "created_at": intake.created_at.isoformat() if intake.created_at else None,
        }
    
    # =========================================================================
    # SCHEMA SCORES (All)
    # =========================================================================
    schema_scores = []
    schemas = (
        db.query(models.SchemaItemResponse)
        .filter(models.SchemaItemResponse.user_hash == user_hash)
        .order_by(models.SchemaItemResponse.created_at.desc())
        .all()
    )
    for s in schemas:
        schema_scores.append({
            "id": s.id,
            "schema_key": s.schema_key,
            "prompt": s.prompt,
            "score": s.score,
            "note": s.note,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    
    # =========================================================================
    # PHQ-9 SCORES (All)
    # =========================================================================
    phq9_scores = []
    phq9s = (
        db.query(models.Phq9ItemResponse)
        .filter(models.Phq9ItemResponse.user_hash == user_hash)
        .order_by(models.Phq9ItemResponse.question_number.asc())
        .all()
    )
    phq9_total = 0
    for p in phq9s:
        phq9_scores.append({
            "id": p.id,
            "question_number": p.question_number,
            "prompt": p.prompt,
            "score": p.score,
            "note": p.note,
            "is_suicide_item": p.is_suicide_item,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
        phq9_total += p.score or 0
    
    # =========================================================================
    # ML QUESTIONNAIRE (9 personality questions)
    # =========================================================================
    ml_questionnaire = None
    try:
        ml_q = (
            db.query(models.MLQuestionnaireResponse)
            .filter(models.MLQuestionnaireResponse.user_hash == user_hash)
            .first()
        )
        if ml_q:
            ml_questionnaire = {
                "id": ml_q.id,
                "dpes_1": ml_q.dpes_1,
                "dpes_4": ml_q.dpes_4,
                "dpes_29": ml_q.dpes_29,
                "neo_ffi_10": ml_q.neo_ffi_10,
                "neo_ffi_14": ml_q.neo_ffi_14,
                "neo_ffi_16": ml_q.neo_ffi_16,
                "neo_ffi_45": ml_q.neo_ffi_45,
                "neo_ffi_46": ml_q.neo_ffi_46,
                "kamf_4_1": ml_q.kamf_4_1,
                "age": ml_q.age,
                "gender": ml_q.gender,
                "ethnicity": ml_q.ethnicity,
                "education": ml_q.education,
                "depression_status": ml_q.depression_status,
                "created_at": ml_q.created_at.isoformat() if ml_q.created_at else None,
            }
    except Exception as e:
        print(f"[admin] ML questionnaire fetch error: {e}")
    
    # =========================================================================
    # VIDEO SUGGESTIONS (ML recommendations)
    # =========================================================================
    video_suggestions = []
    try:
        suggestions = (
            db.query(models.StimuliSuggestion)
            .filter(models.StimuliSuggestion.user_hash == user_hash)
            .order_by(models.StimuliSuggestion.stimulus_rank.asc())
            .all()
        )
        for s in suggestions:
            video_suggestions.append({
                "id": s.id,
                "stimulus_rank": s.stimulus_rank,
                "stimulus_name": s.stimulus_name,
                "stimulus_url": s.stimulus_url,
                "stimulus_description": s.stimulus_description,
                "score": s.score,
                "was_shown": s.was_shown,
                "was_watched": s.was_watched,
                "was_completed": s.was_completed,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Video suggestions fetch error: {e}")
    
    # =========================================================================
    # VIDEO SESSIONS (All watching sessions)
    # =========================================================================
    video_sessions = []
    try:
        v_sessions = (
            db.query(models.VideoSession)
            .filter(models.VideoSession.user_hash == user_hash)
            .order_by(desc(models.VideoSession.started_at))
            .all()
        )
        for vs in v_sessions:
            video_sessions.append({
                "id": vs.id,
                "session_id": vs.session_id,
                "video_id": vs.video_id,
                "started_at": vs.started_at.isoformat() if vs.started_at else None,
                "completed_at": vs.completed_at.isoformat() if vs.completed_at else None,
                "watched_duration_seconds": vs.watched_duration_seconds,
                "completed": vs.completed,
                "chills_count": vs.chills_count,
                "body_map_spots": vs.body_map_spots,
                "has_response": vs.has_response,
            })
    except Exception as e:
        print(f"[admin] Video sessions fetch error: {e}")
    
    # =========================================================================
    # CHILLS TIMESTAMPS (Every chills button press)
    # =========================================================================
    chills_timestamps = []
    try:
        chills = (
            db.query(models.ChillsTimestamp)
            .filter(models.ChillsTimestamp.user_hash == user_hash)
            .order_by(desc(models.ChillsTimestamp.created_at))
            .all()
        )
        for c in chills:
            chills_timestamps.append({
                "id": c.id,
                "session_id": c.session_id,
                "video_time_seconds": c.video_time_seconds,
                "video_name": c.video_name,
                "intensity": c.intensity,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Chills timestamps fetch error: {e}")
    
    # =========================================================================
    # BODY MAP SPOTS (Where they felt chills)
    # =========================================================================
    body_map_spots = []
    try:
        spots = (
            db.query(models.BodyMapSpot)
            .filter(models.BodyMapSpot.session_id.in_(
                db.query(models.VideoSession.session_id)
                .filter(models.VideoSession.user_hash == user_hash)
            ))
            .order_by(desc(models.BodyMapSpot.created_at))
            .all()
        )
        for spot in spots:
            body_map_spots.append({
                "id": spot.id,
                "session_id": spot.session_id,
                "x_percent": spot.x_percent,
                "y_percent": spot.y_percent,
                "created_at": spot.created_at.isoformat() if spot.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Body map spots fetch error: {e}")
    
    # =========================================================================
    # POST-VIDEO RESPONSES (Insights, values, actions)
    # =========================================================================
    post_video_responses = []
    try:
        responses = (
            db.query(models.PostVideoResponse)
            .filter(models.PostVideoResponse.user_hash == user_hash)
            .order_by(desc(models.PostVideoResponse.created_at))
            .all()
        )
        for r_item in responses:
            post_video_responses.append({
                "id": r_item.id,
                "session_id": r_item.session_id,
                "insights_text": r_item.insights_text,
                "value_selected": r_item.value_selected,
                "value_custom": r_item.value_custom,
                "action_selected": r_item.action_selected,
                "action_custom": r_item.action_custom,
                "created_at": r_item.created_at.isoformat() if r_item.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Post-video responses fetch error: {e}")
    
    # =========================================================================
    # ALL SESSIONS (No limit)
    # =========================================================================
    all_sessions = []
    sessions = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(desc(models.Sessions.created_at))
        .all()
    )
    for sess in sessions:
        # Get feedback for this session
        feedback = (
            db.query(models.Feedback)
            .filter(models.Feedback.session_id == sess.id)
            .first()
        )
        feedback_data = None
        if feedback:
            feedback_data = {
                "id": feedback.id,
                "chills": feedback.chills,
                "relevance": feedback.relevance,
                "emotion_word": feedback.emotion_word,
                "chills_option": feedback.chills_option,
                "chills_detail": feedback.chills_detail,
                "session_insight": feedback.session_insight,
            }
        
        all_sessions.append({
            "id": sess.id,
            "track_id": sess.track_id,
            "voice_id": sess.voice_id,
            "audio_path": sess.audio_path,
            "mood": sess.mood,
            "schema_hint": sess.schema_hint,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
            "feedback": feedback_data,
        })
    
    # =========================================================================
    # ALL ACTIVITIES (No limit, with full details)
    # =========================================================================
    all_activities = []
    activity_sessions = (
        db.query(models.ActivitySessions)
        .filter(models.ActivitySessions.user_hash == user_hash)
        .order_by(desc(models.ActivitySessions.created_at))
        .all()
    )
    for act in activity_sessions:
        # Get activity details
        activity_info = (
            db.query(models.Activities)
            .filter(models.Activities.id == act.activity_id)
            .first()
        )
        activity_detail = None
        if activity_info:
            activity_detail = {
                "id": activity_info.id,
                "title": activity_info.title,
                "description": activity_info.description,
                "life_area": activity_info.life_area,
                "effort_level": activity_info.effort_level,
                "reward_type": activity_info.reward_type,
                "default_duration_min": activity_info.default_duration_min,
                "location_label": activity_info.location_label,
                "lat": activity_info.lat,
                "lng": activity_info.lng,
                "place_id": activity_info.place_id,
                "action_intention": activity_info.action_intention,
                "source_type": activity_info.source_type,
            }
        
        all_activities.append({
            "id": act.id,
            "activity_id": act.activity_id,
            "session_id": act.session_id,
            "status": act.status,
            "started_at": act.started_at.isoformat() if act.started_at else None,
            "completed_at": act.completed_at.isoformat() if act.completed_at else None,
            "created_at": act.created_at.isoformat() if act.created_at else None,
            "activity_detail": activity_detail,
        })
    
    # =========================================================================
    # ALL JOURNAL ENTRIES (Full body text, no truncation)
    # =========================================================================
    all_journal = []
    journals = (
        db.query(models.JournalEntries)
        .filter(models.JournalEntries.user_hash == user_hash)
        .order_by(desc(models.JournalEntries.date))
        .all()
    )
    for j in journals:
        all_journal.append({
            "id": j.id,
            "entry_type": j.entry_type,
            "title": j.title,
            "body": j.body,  # Full body, no truncation
            "meta_json": j.meta_json,
            "date": j.date.isoformat() if j.date else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        })
    
    # =========================================================================
    # ALL FEEDBACK (No limit)
    # =========================================================================
    all_feedback = []
    feedbacks = (
        db.query(models.Feedback)
        .join(models.Sessions, models.Sessions.id == models.Feedback.session_id)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(desc(models.Feedback.created_at))
        .all()
    )
    for f in feedbacks:
        all_feedback.append({
            "id": f.id,
            "session_id": f.session_id,
            "chills": f.chills,
            "relevance": f.relevance,
            "emotion_word": f.emotion_word,
            "chills_option": f.chills_option,
            "chills_detail": f.chills_detail,
            "session_insight": f.session_insight,
            "meta_json": f.meta_json,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    
    # =========================================================================
    # MINI CHECK-INS (All)
    # =========================================================================
    mini_checkins = []
    try:
        checkins = (
            db.query(models.MiniCheckins)
            .filter(models.MiniCheckins.user_hash == user_hash)
            .order_by(desc(models.MiniCheckins.created_at))
            .all()
        )
        for mc in checkins:
            mini_checkins.append({
                "id": mc.id,
                "feeling": mc.feeling,
                "body": mc.body,
                "energy": mc.energy,
                "goal_today": mc.goal_today,
                "why_goal": mc.why_goal,
                "last_win": mc.last_win,
                "hard_thing": mc.hard_thing,
                "schema_choice": mc.schema_choice,
                "postal_code": mc.postal_code,
                "place": mc.place,
                "created_at": mc.created_at.isoformat() if mc.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Mini check-ins fetch error: {e}")
    
    # =========================================================================
    # BUILD COMPLETE RESPONSE
    # =========================================================================
    return {
        # Basic info
        "id": user.id,
        "user_hash": user.user_hash,
        "name": user.name,
        "email": user.email,
        "provider": user.provider,
        "journey_day": user.journey_day or 1,
        "onboarding_complete": user.onboarding_complete,
        "ml_questionnaire_complete": user.ml_questionnaire_complete,
        "safety_flag": user.safety_flag,
        "last_phq9_date": user.last_phq9_date.isoformat() if user.last_phq9_date else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        
        # Intake & Assessments
        "intake_data": intake_data,
        "schema_scores": schema_scores,
        "phq9_scores": phq9_scores,
        "phq9_total": phq9_total,
        
        # ML & Video Data
        "ml_questionnaire": ml_questionnaire,
        "video_suggestions": video_suggestions,
        "video_sessions": video_sessions,
        
        # Chills Data
        "chills_timestamps": chills_timestamps,
        "chills_count": len(chills_timestamps),
        "body_map_spots": body_map_spots,
        "post_video_responses": post_video_responses,
        
        # Activity & Journal
        "all_sessions": all_sessions,
        "sessions_count": len(all_sessions),
        "all_activities": all_activities,
        "activities_count": len(all_activities),
        "all_journal": all_journal,
        "journal_count": len(all_journal),
        
        # Feedback & Check-ins
        "all_feedback": all_feedback,
        "feedback_count": len(all_feedback),
        "mini_checkins": mini_checkins,
    }


# =============================================================================
# USER DELETION (SOFT DELETE)
# =============================================================================


@r.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Soft delete a user by setting deleted_at timestamp.
    
    SOFT DELETE BEHAVIOR:
    - Sets deleted_at = current timestamp
    - User cannot sign in anymore
    - User can sign up again with same email (creates new account)
    - Old data preserved for analytics/audit under old user_hash
    - Does NOT delete any related data (sessions, activities, journal, etc.)
    """
    user = db.query(models.Users).filter(models.Users.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check if already deleted
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already deleted",
        )
    
    # Set deleted_at timestamp (soft delete)
    user.deleted_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return {
        "success": True,
        "message": f"User {user.email or user.user_hash} has been deleted",
        "user_id": user.id,
        "deleted_at": user.deleted_at.isoformat(),
    }


# =============================================================================
# SESSIONS
# =============================================================================


@r.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_hash: Optional[str] = Query(None),
):
    """
    List journey sessions with pagination and filters.
    """
    query = db.query(models.Sessions)
    
    # Filter by user
    if user_hash:
        query = query.filter(models.Sessions.user_hash == user_hash)
    
    # Get total count
    total = query.count()
    
    # Sort by most recent
    query = query.order_by(desc(models.Sessions.created_at))
    
    # Paginate
    offset = (page - 1) * page_size
    sessions = query.offset(offset).limit(page_size).all()
    
    # Build response
    items = []
    for sess in sessions:
        # Get user name
        user = (
            db.query(models.Users)
            .filter(models.Users.user_hash == sess.user_hash)
            .first()
        )
        
        # Check if feedback submitted
        feedback = (
            db.query(models.Feedback)
            .filter(models.Feedback.session_id == sess.id)
            .first()
        )
        
        items.append({
            "id": sess.id,
            "user_hash": sess.user_hash,
            "user_name": user.name if user else None,
            "track_id": sess.track_id,
            "mood": sess.mood,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
            "feedback_submitted": feedback is not None,
        })
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# =============================================================================
# ACTIVITIES
# =============================================================================


@r.get("/activities")
def list_activity_completions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_hash: Optional[str] = Query(None),
    completed_only: bool = Query(True),
):
    """
    List user activity completions with pagination.
    """
    query = db.query(models.ActivitySessions)
    
    # Filter by user
    if user_hash:
        query = query.filter(models.ActivitySessions.user_hash == user_hash)
    
    # Filter completed only
    if completed_only:
        query = query.filter(models.ActivitySessions.completed_at.isnot(None))
    
    # Get total count
    total = query.count()
    
    # Sort by most recent
    query = query.order_by(desc(models.ActivitySessions.created_at))
    
    # Paginate
    offset = (page - 1) * page_size
    activities = query.offset(offset).limit(page_size).all()
    
    # Build response
    items = []
    for act in activities:
        # Get user name
        user = (
            db.query(models.Users)
            .filter(models.Users.user_hash == act.user_hash)
            .first()
        )
        
        # Get activity info
        activity_info = (
            db.query(models.Activities)
            .filter(models.Activities.id == act.activity_id)
            .first()
        )
        
        items.append({
            "id": act.id,
            "user_hash": act.user_hash,
            "user_name": user.name if user else None,
            "activity_id": act.activity_id,
            "activity_title": activity_info.title if activity_info else f"Activity #{act.activity_id}",
            "life_area": activity_info.life_area if activity_info else None,
            "started_at": act.started_at.isoformat() if act.started_at else None,
            "completed_at": act.completed_at.isoformat() if act.completed_at else None,
            "status": act.status,
        })
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# =============================================================================
# FEEDBACK DATA
# =============================================================================


@r.get("/feedback")
def list_feedback(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List feedback entries with pagination.
    """
    query = db.query(models.Feedback)
    
    # Get total count
    total = query.count()
    
    # Sort by most recent
    query = query.order_by(desc(models.Feedback.created_at))
    
    # Paginate
    offset = (page - 1) * page_size
    feedback_list = query.offset(offset).limit(page_size).all()
    
    # Build response
    items = []
    for f in feedback_list:
        # Get session info
        session = (
            db.query(models.Sessions)
            .filter(models.Sessions.id == f.session_id)
            .first()
        )
        
        user_name = None
        if session:
            user = (
                db.query(models.Users)
                .filter(models.Users.user_hash == session.user_hash)
                .first()
            )
            user_name = user.name if user else None
        
        items.append({
            "id": f.id,
            "session_id": f.session_id,
            "user_name": user_name,
            "chills": f.chills,
            "relevance": f.relevance,
            "emotion_word": f.emotion_word,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# =============================================================================
# JOURNAL ENTRIES
# =============================================================================


@r.get("/journal")
def list_journal_entries(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_hash: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
):
    """
    List journal entries with pagination.
    """
    query = db.query(models.JournalEntries)
    
    # Filter by user
    if user_hash:
        query = query.filter(models.JournalEntries.user_hash == user_hash)
    
    # Filter by entry type
    if entry_type:
        query = query.filter(models.JournalEntries.entry_type == entry_type)
    
    # Get total count
    total = query.count()
    
    # Sort by most recent
    query = query.order_by(desc(models.JournalEntries.date))
    
    # Paginate
    offset = (page - 1) * page_size
    entries = query.offset(offset).limit(page_size).all()
    
    # Build response
    items = []
    for e in entries:
        # Get user name
        user = (
            db.query(models.Users)
            .filter(models.Users.user_hash == e.user_hash)
            .first()
        )
        
        items.append({
            "id": e.id,
            "user_hash": e.user_hash,
            "user_name": user.name if user else None,
            "entry_type": e.entry_type,
            "title": e.title,
            "body": e.body[:300] if e.body else None,
            "date": e.date.isoformat() if e.date else None,
        })
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# =============================================================================
# CSV EXPORT ENDPOINTS
# =============================================================================


def _generate_csv(data: List[dict], filename: str) -> StreamingResponse:
    """Helper to generate CSV streaming response."""
    if not data:
        output = io.StringIO()
        output.write("No data available\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@r.get("/export/users")
def export_users_csv(
    db: Session = Depends(get_db),
    include_deleted: bool = Query(False),
):
    """Export all users as CSV."""
    query = db.query(models.Users)
    
    if not include_deleted:
        query = query.filter(models.Users.deleted_at.is_(None))
    
    users = query.order_by(desc(models.Users.created_at)).all()
    
    data = []
    for user in users:
        session_count = (
            db.query(func.count(models.Sessions.id))
            .filter(models.Sessions.user_hash == user.user_hash)
            .scalar() or 0
        )
        
        activity_count = (
            db.query(func.count(models.ActivitySessions.id))
            .filter(
                models.ActivitySessions.user_hash == user.user_hash,
                models.ActivitySessions.completed_at.isnot(None),
            )
            .scalar() or 0
        )
        
        chills_count = 0
        try:
            chills_count = (
                db.query(func.count(models.ChillsTimestamp.id))
                .filter(models.ChillsTimestamp.user_hash == user.user_hash)
                .scalar() or 0
            )
        except Exception:
            pass
        
        data.append({
            "id": user.id,
            "user_hash": user.user_hash,
            "name": user.name,
            "email": user.email,
            "provider": user.provider,
            "journey_day": user.journey_day or 1,
            "onboarding_complete": user.onboarding_complete,
            "ml_questionnaire_complete": user.ml_questionnaire_complete,
            "safety_flag": user.safety_flag,
            "total_sessions": session_count,
            "total_activities": activity_count,
            "total_chills": chills_count,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        })
    
    return _generate_csv(data, "rewire_users.csv")


@r.get("/export/users/{user_id}")
def export_user_complete_csv(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Export complete data for a single user as CSV."""
    user = db.query(models.Users).filter(models.Users.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user_hash = user.user_hash
    output = io.StringIO()
    
    # Write user info
    output.write("=== USER INFO ===\n")
    output.write(f"ID,{user.id}\n")
    output.write(f"User Hash,{user.user_hash}\n")
    output.write(f"Name,{user.name}\n")
    output.write(f"Email,{user.email}\n")
    output.write(f"Provider,{user.provider}\n")
    output.write(f"Journey Day,{user.journey_day or 1}\n")
    output.write(f"Onboarding Complete,{user.onboarding_complete}\n")
    output.write(f"ML Questionnaire Complete,{user.ml_questionnaire_complete}\n")
    output.write(f"Safety Flag,{user.safety_flag}\n")
    output.write(f"Created At,{user.created_at.isoformat() if user.created_at else ''}\n")
    output.write("\n")
    
    # Intake data
    output.write("=== INTAKE DATA ===\n")
    intake = db.query(models.ClinicalIntake).filter(models.ClinicalIntake.user_hash == user_hash).first()
    if intake:
        output.write(f"Age,{intake.age}\n")
        output.write(f"Gender,{intake.gender}\n")
        output.write(f"Postal Code,{intake.postal_code}\n")
        output.write(f"In Therapy,{intake.in_therapy}\n")
        output.write(f"On Medication,{intake.on_medication}\n")
        output.write(f"Psychosis History,{intake.psychosis_history}\n")
        output.write(f"Pregnant or Planning,{intake.pregnant_or_planning}\n")
        output.write(f"Life Area,{intake.life_area}\n")
        output.write(f"Life Focus,{intake.life_focus}\n")
        pre_intake = (intake.pre_intake_text or '').replace('"', '""').replace('\n', ' ')
        output.write(f"Pre-Intake Text,\"{pre_intake}\"\n")
    output.write("\n")
    
    # PHQ-9
    output.write("=== PHQ-9 SCORES ===\n")
    output.write("Question Number,Score,Is Suicide Item,Created At\n")
    phq9s = db.query(models.Phq9ItemResponse).filter(models.Phq9ItemResponse.user_hash == user_hash).order_by(models.Phq9ItemResponse.question_number).all()
    for p in phq9s:
        output.write(f"{p.question_number},{p.score},{p.is_suicide_item},{p.created_at.isoformat() if p.created_at else ''}\n")
    output.write("\n")
    
    # ML Questionnaire
    output.write("=== ML QUESTIONNAIRE ===\n")
    try:
        ml_q = db.query(models.MLQuestionnaireResponse).filter(models.MLQuestionnaireResponse.user_hash == user_hash).first()
        if ml_q:
            output.write(f"DPES_1,{ml_q.dpes_1}\n")
            output.write(f"DPES_4,{ml_q.dpes_4}\n")
            output.write(f"DPES_29,{ml_q.dpes_29}\n")
            output.write(f"NEO_FFI_10,{ml_q.neo_ffi_10}\n")
            output.write(f"NEO_FFI_14,{ml_q.neo_ffi_14}\n")
            output.write(f"NEO_FFI_16,{ml_q.neo_ffi_16}\n")
            output.write(f"NEO_FFI_45,{ml_q.neo_ffi_45}\n")
            output.write(f"NEO_FFI_46,{ml_q.neo_ffi_46}\n")
            output.write(f"KAMF_4_1,{ml_q.kamf_4_1}\n")
    except Exception:
        pass
    output.write("\n")
    
    # Video Suggestions
    output.write("=== VIDEO SUGGESTIONS ===\n")
    output.write("Rank,Video Name,Score,URL,Was Watched,Was Completed\n")
    try:
        suggestions = db.query(models.StimuliSuggestion).filter(models.StimuliSuggestion.user_hash == user_hash).order_by(models.StimuliSuggestion.stimulus_rank).all()
        for s in suggestions:
            name = (s.stimulus_name or '').replace('"', '""')
            output.write(f"{s.stimulus_rank},\"{name}\",{s.score},{s.stimulus_url},{s.was_watched},{s.was_completed}\n")
    except Exception:
        pass
    output.write("\n")
    
    # Chills Timestamps
    output.write("=== CHILLS TIMESTAMPS ===\n")
    output.write("Session ID,Video Time (seconds),Video Name,Intensity,Created At\n")
    try:
        chills = db.query(models.ChillsTimestamp).filter(models.ChillsTimestamp.user_hash == user_hash).order_by(desc(models.ChillsTimestamp.created_at)).all()
        for c in chills:
            video_name = (c.video_name or '').replace('"', '""')
            output.write(f"{c.session_id},{c.video_time_seconds},\"{video_name}\",{c.intensity or ''},{c.created_at.isoformat() if c.created_at else ''}\n")
    except Exception:
        pass
    output.write("\n")
    
    # Body Map Spots
    output.write("=== BODY MAP SPOTS ===\n")
    output.write("Session ID,X Percent,Y Percent,Created At\n")
    try:
        spots = db.query(models.BodyMapSpot).filter(
            models.BodyMapSpot.session_id.in_(
                db.query(models.VideoSession.session_id).filter(models.VideoSession.user_hash == user_hash)
            )
        ).all()
        for spot in spots:
            output.write(f"{spot.session_id},{spot.x_percent},{spot.y_percent},{spot.created_at.isoformat() if spot.created_at else ''}\n")
    except Exception:
        pass
    output.write("\n")
    
    # Post-Video Responses
    output.write("=== POST-VIDEO RESPONSES ===\n")
    output.write("Session ID,Insights,Value Selected,Value Custom,Action Selected,Action Custom,Created At\n")
    try:
        responses = db.query(models.PostVideoResponse).filter(models.PostVideoResponse.user_hash == user_hash).order_by(desc(models.PostVideoResponse.created_at)).all()
        for r_item in responses:
            insights = (r_item.insights_text or '').replace('"', '""').replace('\n', ' ')
            output.write(f"{r_item.session_id},\"{insights}\",{r_item.value_selected or ''},{r_item.value_custom or ''},{r_item.action_selected or ''},{r_item.action_custom or ''},{r_item.created_at.isoformat() if r_item.created_at else ''}\n")
    except Exception:
        pass
    output.write("\n")
    
    # Activities
    output.write("=== ACTIVITIES ===\n")
    output.write("Activity ID,Title,Life Area,Status,Started At,Completed At\n")
    activities = db.query(models.ActivitySessions).filter(models.ActivitySessions.user_hash == user_hash).order_by(desc(models.ActivitySessions.created_at)).all()
    for act in activities:
        activity_info = db.query(models.Activities).filter(models.Activities.id == act.activity_id).first()
        title = (activity_info.title if activity_info else f"Activity #{act.activity_id}").replace('"', '""')
        life_area = activity_info.life_area if activity_info else ""
        output.write(f"{act.activity_id},\"{title}\",{life_area},{act.status},{act.started_at.isoformat() if act.started_at else ''},{act.completed_at.isoformat() if act.completed_at else ''}\n")
    output.write("\n")
    
    # Journal Entries
    output.write("=== JOURNAL ENTRIES ===\n")
    output.write("ID,Type,Title,Body,Date\n")
    journals = db.query(models.JournalEntries).filter(models.JournalEntries.user_hash == user_hash).order_by(desc(models.JournalEntries.date)).all()
    for j in journals:
        body = (j.body or '').replace('"', '""').replace('\n', ' ')
        title = (j.title or '').replace('"', '""')
        output.write(f"{j.id},{j.entry_type},\"{title}\",\"{body}\",{j.date.isoformat() if j.date else ''}\n")
    
    output.seek(0)
    
    filename = f"rewire_user_{user_id}_complete.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@r.get("/export/chills")
def export_chills_csv(
    db: Session = Depends(get_db),
):
    """Export all chills data as CSV."""
    data = []
    
    try:
        chills = db.query(models.ChillsTimestamp).order_by(desc(models.ChillsTimestamp.created_at)).all()
        for c in chills:
            user = None
            if c.user_hash:
                user = db.query(models.Users).filter(models.Users.user_hash == c.user_hash).first()
            
            data.append({
                "id": c.id,
                "user_hash": c.user_hash,
                "user_name": user.name if user else None,
                "user_email": user.email if user else None,
                "session_id": c.session_id,
                "video_time_seconds": c.video_time_seconds,
                "video_name": c.video_name,
                "intensity": c.intensity,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Chills export error: {e}")
    
    return _generate_csv(data, "rewire_chills.csv")


@r.get("/export/activities")
def export_activities_csv(
    db: Session = Depends(get_db),
):
    """Export all activity completions as CSV."""
    data = []
    
    activities = db.query(models.ActivitySessions).order_by(desc(models.ActivitySessions.created_at)).all()
    for act in activities:
        user = db.query(models.Users).filter(models.Users.user_hash == act.user_hash).first()
        activity_info = db.query(models.Activities).filter(models.Activities.id == act.activity_id).first()
        
        data.append({
            "id": act.id,
            "user_hash": act.user_hash,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "activity_id": act.activity_id,
            "activity_title": activity_info.title if activity_info else None,
            "activity_description": activity_info.description if activity_info else None,
            "life_area": activity_info.life_area if activity_info else None,
            "effort_level": activity_info.effort_level if activity_info else None,
            "location_label": activity_info.location_label if activity_info else None,
            "status": act.status,
            "started_at": act.started_at.isoformat() if act.started_at else None,
            "completed_at": act.completed_at.isoformat() if act.completed_at else None,
            "created_at": act.created_at.isoformat() if act.created_at else None,
        })
    
    return _generate_csv(data, "rewire_activities.csv")


@r.get("/export/journal")
def export_journal_csv(
    db: Session = Depends(get_db),
):
    """Export all journal entries as CSV."""
    data = []
    
    entries = db.query(models.JournalEntries).order_by(desc(models.JournalEntries.date)).all()
    for e in entries:
        user = db.query(models.Users).filter(models.Users.user_hash == e.user_hash).first()
        
        data.append({
            "id": e.id,
            "user_hash": e.user_hash,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "entry_type": e.entry_type,
            "title": e.title,
            "body": e.body,
            "date": e.date.isoformat() if e.date else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })
    
    return _generate_csv(data, "rewire_journal.csv")


@r.get("/export/intake")
def export_intake_csv(
    db: Session = Depends(get_db),
):
    """Export all intake data as CSV."""
    data = []
    
    intakes = db.query(models.ClinicalIntake).order_by(desc(models.ClinicalIntake.created_at)).all()
    for intake in intakes:
        user = db.query(models.Users).filter(models.Users.user_hash == intake.user_hash).first()
        
        data.append({
            "id": intake.id,
            "user_hash": intake.user_hash,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "age": intake.age,
            "gender": intake.gender,
            "postal_code": intake.postal_code,
            "in_therapy": intake.in_therapy,
            "therapy_type": intake.therapy_type,
            "on_medication": intake.on_medication,
            "medication_list": intake.medication_list,
            "psychosis_history": intake.psychosis_history,
            "pregnant_or_planning": intake.pregnant_or_planning,
            "life_area": intake.life_area,
            "life_focus": intake.life_focus,
            "pre_intake_text": intake.pre_intake_text,
            "good_life_answer": intake.good_life_answer,
            "created_at": intake.created_at.isoformat() if intake.created_at else None,
        })
    
    return _generate_csv(data, "rewire_intake.csv")


@r.get("/export/ml-questionnaire")
def export_ml_questionnaire_csv(
    db: Session = Depends(get_db),
):
    """Export all ML questionnaire responses as CSV."""
    data = []
    
    try:
        responses = db.query(models.MLQuestionnaireResponse).order_by(desc(models.MLQuestionnaireResponse.created_at)).all()
        for ml_q in responses:
            user = db.query(models.Users).filter(models.Users.user_hash == ml_q.user_hash).first()
            
            data.append({
                "id": ml_q.id,
                "user_hash": ml_q.user_hash,
                "user_name": user.name if user else None,
                "user_email": user.email if user else None,
                "dpes_1": ml_q.dpes_1,
                "dpes_4": ml_q.dpes_4,
                "dpes_29": ml_q.dpes_29,
                "neo_ffi_10": ml_q.neo_ffi_10,
                "neo_ffi_14": ml_q.neo_ffi_14,
                "neo_ffi_16": ml_q.neo_ffi_16,
                "neo_ffi_45": ml_q.neo_ffi_45,
                "neo_ffi_46": ml_q.neo_ffi_46,
                "kamf_4_1": ml_q.kamf_4_1,
                "age": ml_q.age,
                "gender": ml_q.gender,
                "ethnicity": ml_q.ethnicity,
                "education": ml_q.education,
                "depression_status": ml_q.depression_status,
                "created_at": ml_q.created_at.isoformat() if ml_q.created_at else None,
            })
    except Exception as e:
        print(f"[admin] ML questionnaire export error: {e}")
    
    return _generate_csv(data, "rewire_ml_questionnaire.csv")


@r.get("/export/video-sessions")
def export_video_sessions_csv(
    db: Session = Depends(get_db),
):
    """Export all video sessions as CSV."""
    data = []
    
    try:
        sessions = db.query(models.VideoSession).order_by(desc(models.VideoSession.started_at)).all()
        for vs in sessions:
            user = db.query(models.Users).filter(models.Users.user_hash == vs.user_hash).first()
            
            video = None
            try:
                video = db.query(models.VideoStimulus).filter(models.VideoStimulus.id == vs.video_id).first()
            except Exception:
                pass
            
            data.append({
                "id": vs.id,
                "session_id": vs.session_id,
                "user_hash": vs.user_hash,
                "user_name": user.name if user else None,
                "user_email": user.email if user else None,
                "video_id": vs.video_id,
                "video_name": video.stimulus_name if video else None,
                "started_at": vs.started_at.isoformat() if vs.started_at else None,
                "completed_at": vs.completed_at.isoformat() if vs.completed_at else None,
                "watched_duration_seconds": vs.watched_duration_seconds,
                "completed": vs.completed,
                "chills_count": vs.chills_count,
                "body_map_spots": vs.body_map_spots,
                "has_response": vs.has_response,
            })
    except Exception as e:
        print(f"[admin] Video sessions export error: {e}")
    
    return _generate_csv(data, "rewire_video_sessions.csv")


@r.get("/export/feedback")
def export_feedback_csv(
    db: Session = Depends(get_db),
):
    """Export all feedback as CSV."""
    data = []
    
    feedbacks = db.query(models.Feedback).order_by(desc(models.Feedback.created_at)).all()
    for f in feedbacks:
        session = db.query(models.Sessions).filter(models.Sessions.id == f.session_id).first()
        user = None
        if session:
            user = db.query(models.Users).filter(models.Users.user_hash == session.user_hash).first()
        
        data.append({
            "id": f.id,
            "session_id": f.session_id,
            "user_hash": session.user_hash if session else None,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "chills": f.chills,
            "relevance": f.relevance,
            "emotion_word": f.emotion_word,
            "chills_option": f.chills_option,
            "chills_detail": f.chills_detail,
            "session_insight": f.session_insight,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    
    return _generate_csv(data, "rewire_feedback.csv")


@r.get("/export/post-video-responses")
def export_post_video_responses_csv(
    db: Session = Depends(get_db),
):
    """Export all post-video responses as CSV."""
    data = []
    
    try:
        responses = db.query(models.PostVideoResponse).order_by(desc(models.PostVideoResponse.created_at)).all()
        for r_item in responses:
            user = None
            if r_item.user_hash:
                user = db.query(models.Users).filter(models.Users.user_hash == r_item.user_hash).first()
            
            data.append({
                "id": r_item.id,
                "session_id": r_item.session_id,
                "user_hash": r_item.user_hash,
                "user_name": user.name if user else None,
                "user_email": user.email if user else None,
                "insights_text": r_item.insights_text,
                "value_selected": r_item.value_selected,
                "value_custom": r_item.value_custom,
                "action_selected": r_item.action_selected,
                "action_custom": r_item.action_custom,
                "created_at": r_item.created_at.isoformat() if r_item.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Post-video responses export error: {e}")
    
    return _generate_csv(data, "rewire_post_video_responses.csv")


@r.get("/export/body-map")
def export_body_map_csv(
    db: Session = Depends(get_db),
):
    """Export all body map spots as CSV."""
    data = []
    
    try:
        spots = db.query(models.BodyMapSpot).order_by(desc(models.BodyMapSpot.created_at)).all()
        for spot in spots:
            user = None
            try:
                video_session = db.query(models.VideoSession).filter(models.VideoSession.session_id == spot.session_id).first()
                if video_session and video_session.user_hash:
                    user = db.query(models.Users).filter(models.Users.user_hash == video_session.user_hash).first()
            except Exception:
                pass
            
            data.append({
                "id": spot.id,
                "session_id": spot.session_id,
                "user_name": user.name if user else None,
                "user_email": user.email if user else None,
                "x_percent": spot.x_percent,
                "y_percent": spot.y_percent,
                "created_at": spot.created_at.isoformat() if spot.created_at else None,
            })
    except Exception as e:
        print(f"[admin] Body map export error: {e}")
    
    return _generate_csv(data, "rewire_body_map.csv")
