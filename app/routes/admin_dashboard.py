# routes/admin_dashboard.py
# CHANGE #10: Admin Console Dashboard Routes
"""
Admin dashboard endpoints for the ReWire Admin Console.
Provides statistics, user management, and data viewing capabilities.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..auth_utils import get_db, require_admin
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
    users_with_chills: int


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
    total_chills: int


class UserDetail(BaseModel):
    id: int
    user_hash: str
    name: Optional[str] = None
    email: Optional[str] = None
    journey_day: int
    created_at: Optional[datetime] = None
    intake_data: Optional[dict] = None
    schema_scores: Optional[List[dict]] = None
    phq9_scores: Optional[List[dict]] = None
    recent_sessions: Optional[List[dict]] = None
    recent_activities: Optional[List[dict]] = None
    recent_journal: Optional[List[dict]] = None
    chills_history: Optional[List[dict]] = None


class SessionSummary(BaseModel):
    id: int
    user_hash: str
    user_name: Optional[str] = None
    session_number: int
    created_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    chills_count: int
    feedback_submitted: bool


class ActivitySummary(BaseModel):
    id: int
    user_hash: str
    user_name: Optional[str] = None
    activity_title: str
    life_area: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str


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
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get dashboard statistics overview.
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    
    # Total users
    total_users = db.query(func.count(models.Users.id)).scalar() or 0
    
    # Active users today (users with sessions or activities today)
    active_today_sessions = (
        db.query(func.count(func.distinct(models.JourneySessions.user_hash)))
        .filter(models.JourneySessions.created_at >= today_start)
        .scalar() or 0
    )
    
    # Active users this week
    active_week_sessions = (
        db.query(func.count(func.distinct(models.JourneySessions.user_hash)))
        .filter(models.JourneySessions.created_at >= week_ago)
        .scalar() or 0
    )
    
    # Total sessions
    total_sessions = db.query(func.count(models.JourneySessions.id)).scalar() or 0
    
    # Sessions today
    sessions_today = (
        db.query(func.count(models.JourneySessions.id))
        .filter(models.JourneySessions.created_at >= today_start)
        .scalar() or 0
    )
    
    # Total activities completed
    total_activities = (
        db.query(func.count(models.UserActivities.id))
        .filter(models.UserActivities.completed_at.isnot(None))
        .scalar() or 0
    )
    
    # Activities completed today
    activities_today = (
        db.query(func.count(models.UserActivities.id))
        .filter(
            models.UserActivities.completed_at.isnot(None),
            models.UserActivities.completed_at >= today_start,
        )
        .scalar() or 0
    )
    
    # Total journal entries
    total_journal = db.query(func.count(models.JournalEntries.id)).scalar() or 0
    
    # Average sessions per user
    avg_sessions = 0.0
    if total_users > 0:
        avg_sessions = round(total_sessions / total_users, 2)
    
    # Users who have experienced chills
    users_with_chills = (
        db.query(func.count(func.distinct(models.ChillsMoments.user_hash)))
        .scalar() or 0
    )
    
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
        users_with_chills=users_with_chills,
    )


# =============================================================================
# USER MANAGEMENT
# =============================================================================


@r.get("/users")
def list_users(
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|name|journey_day|last_active)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
):
    """
    List all users with pagination and search.
    """
    query = db.query(models.Users)
    
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
    sort_column = getattr(models.Users, sort_by, models.Users.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Paginate
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()
    
    # Build response with additional stats
    items = []
    for user in users:
        # Count sessions for this user
        session_count = (
            db.query(func.count(models.JourneySessions.id))
            .filter(models.JourneySessions.user_hash == user.user_hash)
            .scalar() or 0
        )
        
        # Count completed activities
        activity_count = (
            db.query(func.count(models.UserActivities.id))
            .filter(
                models.UserActivities.user_hash == user.user_hash,
                models.UserActivities.completed_at.isnot(None),
            )
            .scalar() or 0
        )
        
        # Count chills
        chills_count = (
            db.query(func.count(models.ChillsMoments.id))
            .filter(models.ChillsMoments.user_hash == user.user_hash)
            .scalar() or 0
        )
        
        # Get last activity
        last_session = (
            db.query(models.JourneySessions.created_at)
            .filter(models.JourneySessions.user_hash == user.user_hash)
            .order_by(desc(models.JourneySessions.created_at))
            .first()
        )
        
        items.append(UserSummary(
            id=user.id,
            user_hash=user.user_hash,
            name=user.name,
            email=user.email,
            journey_day=user.journey_day or 1,
            created_at=user.created_at,
            last_active=last_session[0] if last_session else user.created_at,
            total_sessions=session_count,
            total_activities=activity_count,
            total_chills=chills_count,
        ))
    
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "items": [item.dict() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@r.get("/users/{user_id}")
def get_user_detail(
    user_id: int,
    admin: dict = Depends(require_admin),
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
        db.query(models.Intake)
        .filter(models.Intake.user_hash == user.user_hash)
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
        db.query(models.SchemaAnswers)
        .filter(models.SchemaAnswers.user_hash == user.user_hash)
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
        db.query(models.PHQ9Answers)
        .filter(models.PHQ9Answers.user_hash == user.user_hash)
        .all()
    )
    for p in phq9s:
        phq9_scores.append({
            "question_index": p.question_index,
            "score": p.score,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    
    # Get recent sessions
    recent_sessions = []
    sessions = (
        db.query(models.JourneySessions)
        .filter(models.JourneySessions.user_hash == user.user_hash)
        .order_by(desc(models.JourneySessions.created_at))
        .limit(10)
        .all()
    )
    for sess in sessions:
        chills_count = (
            db.query(func.count(models.ChillsMoments.id))
            .filter(models.ChillsMoments.session_id == sess.id)
            .scalar() or 0
        )
        recent_sessions.append({
            "id": sess.id,
            "session_number": sess.session_number,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
            "duration_seconds": sess.duration_seconds,
            "chills_count": chills_count,
        })
    
    # Get recent activities
    recent_activities = []
    activities = (
        db.query(models.UserActivities)
        .filter(models.UserActivities.user_hash == user.user_hash)
        .order_by(desc(models.UserActivities.created_at))
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
            "status": "completed" if act.completed_at else "started",
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
            "body": j.body[:200] if j.body else None,  # Truncate for preview
            "date": j.date.isoformat() if j.date else None,
        })
    
    # Get chills history
    chills_history = []
    chills = (
        db.query(models.ChillsMoments)
        .filter(models.ChillsMoments.user_hash == user.user_hash)
        .order_by(desc(models.ChillsMoments.created_at))
        .limit(20)
        .all()
    )
    for c in chills:
        chills_history.append({
            "id": c.id,
            "session_id": c.session_id,
            "timestamp_seconds": c.timestamp_seconds,
            "intensity": c.intensity,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    
    return {
        "id": user.id,
        "user_hash": user.user_hash,
        "name": user.name,
        "email": user.email,
        "journey_day": user.journey_day or 1,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "intake_data": intake_data,
        "schema_scores": schema_scores,
        "phq9_scores": phq9_scores,
        "recent_sessions": recent_sessions,
        "recent_activities": recent_activities,
        "recent_journal": recent_journal,
        "chills_history": chills_history,
    }


# =============================================================================
# SESSIONS
# =============================================================================


@r.get("/sessions")
def list_sessions(
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_hash: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """
    List journey sessions with pagination and filters.
    """
    query = db.query(models.JourneySessions)
    
    # Filter by user
    if user_hash:
        query = query.filter(models.JourneySessions.user_hash == user_hash)
    
    # Filter by date range
    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from)
            query = query.filter(models.JourneySessions.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to)
            query = query.filter(models.JourneySessions.created_at <= to_date)
        except ValueError:
            pass
    
    # Get total count
    total = query.count()
    
    # Sort by most recent
    query = query.order_by(desc(models.JourneySessions.created_at))
    
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
        
        # Count chills
        chills_count = (
            db.query(func.count(models.ChillsMoments.id))
            .filter(models.ChillsMoments.session_id == sess.id)
            .scalar() or 0
        )
        
        # Check if feedback submitted
        feedback = (
            db.query(models.SessionFeedback)
            .filter(models.SessionFeedback.session_id == sess.id)
            .first()
        )
        
        items.append({
            "id": sess.id,
            "user_hash": sess.user_hash,
            "user_name": user.name if user else None,
            "session_number": sess.session_number,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
            "duration_seconds": sess.duration_seconds,
            "chills_count": chills_count,
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
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_hash: Optional[str] = Query(None),
    completed_only: bool = Query(True),
):
    """
    List user activity completions with pagination.
    """
    query = db.query(models.UserActivities)
    
    # Filter by user
    if user_hash:
        query = query.filter(models.UserActivities.user_hash == user_hash)
    
    # Filter completed only
    if completed_only:
        query = query.filter(models.UserActivities.completed_at.isnot(None))
    
    # Get total count
    total = query.count()
    
    # Sort by most recent
    query = query.order_by(desc(models.UserActivities.created_at))
    
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
            "status": "completed" if act.completed_at else "started",
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
# CHILLS DATA
# =============================================================================


@r.get("/chills")
def list_chills_moments(
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_hash: Optional[str] = Query(None),
):
    """
    List chills moments with pagination.
    """
    query = db.query(models.ChillsMoments)
    
    # Filter by user
    if user_hash:
        query = query.filter(models.ChillsMoments.user_hash == user_hash)
    
    # Get total count
    total = query.count()
    
    # Sort by most recent
    query = query.order_by(desc(models.ChillsMoments.created_at))
    
    # Paginate
    offset = (page - 1) * page_size
    chills = query.offset(offset).limit(page_size).all()
    
    # Build response
    items = []
    for c in chills:
        # Get user name
        user = (
            db.query(models.Users)
            .filter(models.Users.user_hash == c.user_hash)
            .first()
        )
        
        items.append({
            "id": c.id,
            "user_hash": c.user_hash,
            "user_name": user.name if user else None,
            "session_id": c.session_id,
            "timestamp_seconds": c.timestamp_seconds,
            "intensity": c.intensity,
            "created_at": c.created_at.isoformat() if c.created_at else None,
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
    admin: dict = Depends(require_admin),
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
            "body": e.body[:300] if e.body else None,  # Truncate for preview
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
