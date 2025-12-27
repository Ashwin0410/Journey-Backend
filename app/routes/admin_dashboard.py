# routes/admin_dashboard.py
# CHANGE #10: Admin Console Dashboard Routes (No Auth Required)
"""
Admin dashboard endpoints for the ReWire Admin Console.
Provides statistics, user management, and data viewing capabilities.
NO AUTHENTICATION - Direct access for simplicity.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

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


@r.get("/stats", response_model=DashboardStats)
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
    
    return DashboardStats(
        total_users=total_users,
        active_users_today=active_today_sessions,
        active_users_week=active_week_sessions,
        total_sessions=total_sessions,
        sessions_today=sessions_today,
        total_activities_completed=total_activities,
        activities_today=activities_today,
        total_journal_entries=total_journal,
        avg_sessions_per_user=avg_sessions,
        total_feedback=total_feedback,
    )


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
    Get detailed information for a specific user.
    """
    user = db.query(models.Users).filter(models.Users.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Get intake data
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user.user_hash)
        .first()
    )
    
    intake_data = None
    if intake:
        intake_data = {
            "age": intake.age,
            "gender": intake.gender,
            "postal_code": intake.postal_code,
            "in_therapy": intake.in_therapy,
            "on_medication": intake.on_medication,
            "life_area": intake.life_area,
            "life_focus": intake.life_focus,
            "week_plan_text": intake.week_plan_text,
        }
    
    # Get schema scores
    schema_scores = []
    schemas = (
        db.query(models.SchemaItemResponse)
        .filter(models.SchemaItemResponse.user_hash == user.user_hash)
        .all()
    )
    for s in schemas:
        schema_scores.append({
            "schema_key": s.schema_key,
            "score": s.score,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    
    # Get PHQ-9 scores
    phq9_scores = []
    phq9s = (
        db.query(models.Phq9ItemResponse)
        .filter(models.Phq9ItemResponse.user_hash == user.user_hash)
        .all()
    )
    for p in phq9s:
        phq9_scores.append({
            "question_number": p.question_number,
            "score": p.score,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    
    # Get recent sessions
    recent_sessions = []
    sessions = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user.user_hash)
        .order_by(desc(models.Sessions.created_at))
        .limit(10)
        .all()
    )
    for sess in sessions:
        recent_sessions.append({
            "id": sess.id,
            "track_id": sess.track_id,
            "mood": sess.mood,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
        })
    
    # Get recent activities
    recent_activities = []
    activities = (
        db.query(models.ActivitySessions)
        .filter(models.ActivitySessions.user_hash == user.user_hash)
        .order_by(desc(models.ActivitySessions.created_at))
        .limit(10)
        .all()
    )
    for act in activities:
        # Try to get activity details
        activity_info = (
            db.query(models.Activities)
            .filter(models.Activities.id == act.activity_id)
            .first()
        )
        recent_activities.append({
            "id": act.id,
            "activity_id": act.activity_id,
            "activity_title": activity_info.title if activity_info else f"Activity #{act.activity_id}",
            "started_at": act.started_at.isoformat() if act.started_at else None,
            "completed_at": act.completed_at.isoformat() if act.completed_at else None,
            "status": act.status,
        })
    
    # Get recent journal entries
    recent_journal = []
    journals = (
        db.query(models.JournalEntries)
        .filter(models.JournalEntries.user_hash == user.user_hash)
        .order_by(desc(models.JournalEntries.date))
        .limit(10)
        .all()
    )
    for j in journals:
        recent_journal.append({
            "id": j.id,
            "entry_type": j.entry_type,
            "title": j.title,
            "body": j.body[:200] if j.body else None,
            "date": j.date.isoformat() if j.date else None,
        })
    
    return {
        "id": user.id,
        "user_hash": user.user_hash,
        "name": user.name,
        "email": user.email,
        "journey_day": user.journey_day or 1,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        "intake_data": intake_data,
        "schema_scores": schema_scores,
        "phq9_scores": phq9_scores,
        "recent_sessions": recent_sessions,
        "recent_activities": recent_activities,
        "recent_journal": recent_journal,
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
