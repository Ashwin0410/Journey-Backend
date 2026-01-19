from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from app.auth_utils import get_current_user
from app.db import SessionLocal
from app import models, schemas
from app.services import narrative

r = APIRouter()


def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def calculate_day_streak(q: Session, user_hash: str) -> int:
    """
    Calculate consecutive days with at least one completed activity.
    Counts backwards from today/yesterday.
    FIX Issue #6: Calculate day streak for timeline stats.
    
    Uses: models.ActivitySessions with user_hash, status, completed_at
    """
    if not user_hash:
        return 0
    
    try:
        # Query distinct dates with completed activities for this user
        completed_dates_query = q.query(
            func.date(models.ActivitySessions.completed_at).label('activity_date')
        ).filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status == "completed",
            models.ActivitySessions.completed_at.isnot(None)
        ).distinct().order_by(
            func.date(models.ActivitySessions.completed_at).desc()
        )
        
        completed_dates = [row.activity_date for row in completed_dates_query.all() if row.activity_date]
        
        if not completed_dates:
            return 0
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Streak only counts if most recent activity was today or yesterday
        most_recent = completed_dates[0]
        if most_recent != today and most_recent != yesterday:
            return 0
        
        # Count consecutive days
        streak = 1
        for i in range(1, len(completed_dates)):
            expected_date = completed_dates[i-1] - timedelta(days=1)
            if completed_dates[i] == expected_date:
                streak += 1
            else:
                break
        
        return streak
        
    except Exception as e:
        print(f"[today.py] Error calculating day streak: {e}")
        return 0


def calculate_activities_completed(q: Session, user_hash: str) -> int:
    """
    Count total completed activities for user.
    FIX Issue #6: Calculate total activities completed for timeline stats.
    
    Uses: models.ActivitySessions with user_hash, status
    """
    if not user_hash:
        return 0
    
    try:
        count = q.query(models.ActivitySessions).filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status == "completed"
        ).count()
        
        return count
        
    except Exception as e:
        print(f"[today.py] Error calculating activities completed: {e}")
        return 0


@r.get("/api/today", response_model=schemas.TodaySummaryOut)
def get_today_summary(
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    # Get base summary from narrative service (existing behavior - unchanged)
    summary = narrative.build_today_summary(q, current_user)
    
    # FIX Issue #6: Calculate and inject stats for day streak and activities
    try:
        user_hash = current_user.user_hash
        day_streak = calculate_day_streak(q, user_hash)
        activities_completed = calculate_activities_completed(q, user_hash)
        
        # Create StatsOut object
        stats_obj = schemas.StatsOut(
            day_streak=day_streak,
            activities_completed=activities_completed
        )
        
        # Add stats to the summary response
        # Handle different response types from narrative.build_today_summary
        
        if hasattr(summary, 'model_dump'):
            # Pydantic v2 model - convert to dict, modify, return
            summary_dict = summary.model_dump()
            summary_dict['stats'] = stats_obj.model_dump()
            return summary_dict
            
        elif hasattr(summary, 'dict'):
            # Pydantic v1 model - convert to dict, modify, return
            summary_dict = summary.dict()
            summary_dict['stats'] = stats_obj.dict()
            return summary_dict
            
        elif isinstance(summary, dict):
            # Dict response
            summary['stats'] = stats_obj.dict() if hasattr(stats_obj, 'dict') else {
                'day_streak': day_streak,
                'activities_completed': activities_completed
            }
            return summary
            
        else:
            # Try to set stats attribute directly
            try:
                summary.stats = stats_obj
            except AttributeError:
                print("[today.py] Could not set stats on summary object")
            
    except Exception as e:
        print(f"[today.py] Error adding stats to summary: {e}")
    
    return summary
