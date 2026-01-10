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


def calculate_day_streak(q: Session, user_id: int) -> int:
    """
    Calculate consecutive days with at least one completed activity.
    Counts backwards from today/yesterday.
    FIX Issue #6: New function to calculate day streak for timeline stats.
    """
    try:
        # Try to find the activity session model
        # Common names: ActivitySession, UserActivitySession, Activity
        activity_model = None
        completed_at_field = None
        user_field = None
        status_field = None
        
        # Check for ActivitySession model
        if hasattr(models, 'ActivitySession'):
            activity_model = models.ActivitySession
            if hasattr(activity_model, 'completed_at'):
                completed_at_field = activity_model.completed_at
            elif hasattr(activity_model, 'created_at'):
                completed_at_field = activity_model.created_at
            if hasattr(activity_model, 'user_id'):
                user_field = activity_model.user_id
            elif hasattr(activity_model, 'user_hash'):
                user_field = None  # Will need different query
            if hasattr(activity_model, 'status'):
                status_field = activity_model.status
        
        # Fallback: check for UserActivity model
        if activity_model is None and hasattr(models, 'UserActivity'):
            activity_model = models.UserActivity
            if hasattr(activity_model, 'completed_at'):
                completed_at_field = activity_model.completed_at
            elif hasattr(activity_model, 'created_at'):
                completed_at_field = activity_model.created_at
            if hasattr(activity_model, 'user_id'):
                user_field = activity_model.user_id
            if hasattr(activity_model, 'status'):
                status_field = activity_model.status
        
        # If we couldn't find a suitable model, return 0
        if activity_model is None or completed_at_field is None:
            print("[today.py] Could not find activity session model for streak calculation")
            return 0
        
        # Build query for completed activities
        query = q.query(
            func.date(completed_at_field).label('activity_date')
        )
        
        # Add user filter
        if user_field is not None:
            query = query.filter(user_field == user_id)
        
        # Add status filter if available
        if status_field is not None:
            query = query.filter(status_field == "completed")
        
        # Filter for non-null completion dates
        query = query.filter(completed_at_field.isnot(None))
        
        # Get distinct dates ordered descending
        query = query.distinct().order_by(
            func.date(completed_at_field).desc()
        )
        
        completed_dates = [row.activity_date for row in query.all() if row.activity_date]
        
        if not completed_dates:
            return 0
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Streak only counts if most recent activity was today or yesterday
        if completed_dates[0] != today and completed_dates[0] != yesterday:
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


def calculate_activities_completed(q: Session, user_id: int) -> int:
    """
    Count total completed activities for user.
    FIX Issue #6: New function to calculate total activities completed.
    """
    try:
        # Try ActivitySession model first
        if hasattr(models, 'ActivitySession'):
            activity_model = models.ActivitySession
            
            query = q.query(activity_model)
            
            # Add user filter
            if hasattr(activity_model, 'user_id'):
                query = query.filter(activity_model.user_id == user_id)
            
            # Add status filter
            if hasattr(activity_model, 'status'):
                query = query.filter(activity_model.status == "completed")
            
            return query.count()
        
        # Fallback: try UserActivity model
        if hasattr(models, 'UserActivity'):
            activity_model = models.UserActivity
            
            query = q.query(activity_model)
            
            if hasattr(activity_model, 'user_id'):
                query = query.filter(activity_model.user_id == user_id)
            
            if hasattr(activity_model, 'status'):
                query = query.filter(activity_model.status == "completed")
            
            return query.count()
        
        return 0
        
    except Exception as e:
        print(f"[today.py] Error calculating activities completed: {e}")
        return 0


@r.get("/api/today", response_model=schemas.TodaySummaryOut)
def get_today_summary(
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    # Get base summary from narrative service (existing behavior)
    summary = narrative.build_today_summary(q, current_user)
    
    # FIX Issue #6: Calculate and inject stats for day streak and activities
    try:
        day_streak = calculate_day_streak(q, current_user.id)
        activities_completed = calculate_activities_completed(q, current_user.id)
        
        # Add stats to the summary response
        # Handle Pydantic model response
        if hasattr(summary, 'stats'):
            if summary.stats is None:
                summary.stats = {}
            if isinstance(summary.stats, dict):
                summary.stats['day_streak'] = day_streak
                summary.stats['activities_completed'] = activities_completed
            elif hasattr(summary.stats, '__dict__'):
                # Stats is an object, try to set attributes
                try:
                    summary.stats.day_streak = day_streak
                    summary.stats.activities_completed = activities_completed
                except AttributeError:
                    pass
        # Handle dict response
        elif isinstance(summary, dict):
            if 'stats' not in summary or summary['stats'] is None:
                summary['stats'] = {}
            summary['stats']['day_streak'] = day_streak
            summary['stats']['activities_completed'] = activities_completed
            
    except Exception as e:
        print(f"[today.py] Error adding stats to summary: {e}")
    
    return summary
