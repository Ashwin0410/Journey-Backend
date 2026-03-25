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


# =============================================================================
# Issue #10: PHQ-9 Recurrence Check
# =============================================================================

PHQ9_RECURRENCE_DAYS = 6  # Felix wants PHQ-9 every 6 days


def check_phq9_due(q: Session, user: models.Users) -> dict:
    """
    Check if a recurring PHQ-9 health check is due for this user.
    
    Issue #10: Felix wants PHQ-9 to recur every 6 days.
    
    Logic:
    1. Check Users.last_phq9_date first (most reliable, updated on each submission)
    2. If null, fall back to checking Phq9ItemResponse table for latest created_at
    3. Also check the new Phq9Assessment table for recurring assessments
    4. If no PHQ-9 has ever been taken, don't flag (they haven't finished onboarding)
    5. If >= PHQ9_RECURRENCE_DAYS since last, return needs_phq9=True
    
    Returns:
        dict with needs_phq9 (bool) and phq9_days_overdue (int)
    """
    if not user or not user.onboarding_complete:
        return {"needs_phq9": False, "phq9_days_overdue": 0}
    
    try:
        today = date.today()
        last_phq9 = None
        
        # Method 1: Check Users.last_phq9_date (set during onboarding and recurring)
        if user.last_phq9_date:
            last_phq9 = user.last_phq9_date
        
        # Method 2: Check Phq9Assessment table (recurring assessments)
        if not last_phq9:
            try:
                latest_assessment = (
                    q.query(models.Phq9Assessment)
                    .filter(models.Phq9Assessment.user_hash == user.user_hash)
                    .order_by(models.Phq9Assessment.created_at.desc())
                    .first()
                )
                if latest_assessment and latest_assessment.created_at:
                    created = latest_assessment.created_at
                    if hasattr(created, 'date'):
                        last_phq9 = created.date() if callable(created.date) else created.date
                    else:
                        last_phq9 = created
            except Exception:
                pass  # Table might not exist yet
        
        # Method 3: Fall back to Phq9ItemResponse table (onboarding PHQ-9)
        if not last_phq9:
            try:
                latest_item = (
                    q.query(models.Phq9ItemResponse)
                    .filter(models.Phq9ItemResponse.user_hash == user.user_hash)
                    .order_by(models.Phq9ItemResponse.created_at.desc())
                    .first()
                )
                if latest_item and latest_item.created_at:
                    created = latest_item.created_at
                    if hasattr(created, 'date'):
                        last_phq9 = created.date() if callable(created.date) else created.date
                    else:
                        last_phq9 = created
            except Exception:
                pass
        
        # If no PHQ-9 has ever been taken, don't flag
        # (user might be legacy or hasn't completed onboarding PHQ-9)
        if not last_phq9:
            return {"needs_phq9": False, "phq9_days_overdue": 0}
        
        # Ensure last_phq9 is a date object
        if isinstance(last_phq9, datetime):
            last_phq9 = last_phq9.date()
        
        # Calculate days since last PHQ-9
        days_since = (today - last_phq9).days
        
        if days_since >= PHQ9_RECURRENCE_DAYS:
            days_overdue = days_since - PHQ9_RECURRENCE_DAYS
            print(f"[today.py] PHQ-9 due for user {user.user_hash}: {days_since} days since last (overdue by {days_overdue})")
            return {
                "needs_phq9": True,
                "phq9_days_overdue": days_overdue,
            }
        
        return {"needs_phq9": False, "phq9_days_overdue": 0}
        
    except Exception as e:
        print(f"[today.py] Error checking PHQ-9 due: {e}")
        return {"needs_phq9": False, "phq9_days_overdue": 0}


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
        
        # =================================================================
        # Issue #10: Check if recurring PHQ-9 is due
        # =================================================================
        phq9_check = check_phq9_due(q, current_user)
        
        # Add stats and PHQ-9 flag to the summary response
        # Handle different response types from narrative.build_today_summary
        
        if hasattr(summary, 'model_dump'):
            # Pydantic v2 model - convert to dict, modify, return
            summary_dict = summary.model_dump()
            summary_dict['stats'] = stats_obj.model_dump()
            summary_dict['needs_phq9'] = phq9_check['needs_phq9']
            summary_dict['phq9_days_overdue'] = phq9_check['phq9_days_overdue']
            return summary_dict
            
        elif hasattr(summary, 'dict'):
            # Pydantic v1 model - convert to dict, modify, return
            summary_dict = summary.dict()
            summary_dict['stats'] = stats_obj.dict()
            summary_dict['needs_phq9'] = phq9_check['needs_phq9']
            summary_dict['phq9_days_overdue'] = phq9_check['phq9_days_overdue']
            return summary_dict
            
        elif isinstance(summary, dict):
            # Dict response
            summary['stats'] = stats_obj.dict() if hasattr(stats_obj, 'dict') else {
                'day_streak': day_streak,
                'activities_completed': activities_completed
            }
            summary['needs_phq9'] = phq9_check['needs_phq9']
            summary['phq9_days_overdue'] = phq9_check['phq9_days_overdue']
            return summary
            
        else:
            # Try to set attributes directly
            try:
                summary.stats = stats_obj
                summary.needs_phq9 = phq9_check['needs_phq9']
                summary.phq9_days_overdue = phq9_check['phq9_days_overdue']
            except AttributeError:
                print("[today.py] Could not set stats/phq9 on summary object")
            
    except Exception as e:
        print(f"[today.py] Error adding stats/phq9 to summary: {e}")
    
    return summary
