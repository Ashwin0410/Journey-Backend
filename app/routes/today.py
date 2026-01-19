from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from typing import List, Optional
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
# FIX Issue #10: Get completed activities for timeline display
# =============================================================================

def get_completed_activities_for_timeline(q: Session, user_hash: str, limit: int = 20) -> List[dict]:
    """
    Get recently completed activities to display in the timeline.
    
    Returns a list of completed activity records with activity details.
    """
    if not user_hash:
        return []
    
    try:
        # Get completed activity sessions with their activity details
        completed_sessions = (
            q.query(models.ActivitySessions)
            .filter(
                models.ActivitySessions.user_hash == user_hash,
                models.ActivitySessions.status == "completed",
                models.ActivitySessions.completed_at.isnot(None)
            )
            .order_by(models.ActivitySessions.completed_at.desc())
            .limit(limit)
            .all()
        )
        
        timeline_entries = []
        
        for session in completed_sessions:
            # Get the activity details
            activity = q.query(models.Activities).filter(
                models.Activities.id == session.activity_id
            ).first()
            
            if activity:
                entry = {
                    "id": session.id,
                    "type": "activity_completed",
                    "title": f"Completed: {activity.title}",
                    "description": activity.description or "",
                    "activity_id": activity.id,
                    "activity_title": activity.title,
                    "location_label": activity.location_label,
                    "life_area": activity.life_area,
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                    "created_at": session.completed_at.isoformat() if session.completed_at else None,
                }
                timeline_entries.append(entry)
        
        return timeline_entries
        
    except Exception as e:
        print(f"[today.py] Error getting completed activities for timeline: {e}")
        return []


def get_journal_entries_for_timeline(q: Session, user_hash: str, limit: int = 20) -> List[dict]:
    """
    Get recent journal entries to display in the timeline.
    
    This includes both user-written entries and auto-generated entries
    (like activity completions).
    """
    if not user_hash:
        return []
    
    try:
        # Get journal entries for this user
        entries = (
            q.query(models.JournalEntries)
            .filter(models.JournalEntries.user_hash == user_hash)
            .order_by(models.JournalEntries.created_at.desc())
            .limit(limit)
            .all()
        )
        
        timeline_entries = []
        
        for entry in entries:
            timeline_entry = {
                "id": entry.id,
                "type": entry.entry_type or "journal",
                "title": entry.title or "Journal Entry",
                "content": entry.content or "",
                "mood": entry.mood,
                "activity_id": entry.activity_id,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
            }
            timeline_entries.append(timeline_entry)
        
        return timeline_entries
        
    except Exception as e:
        print(f"[today.py] Error getting journal entries for timeline: {e}")
        return []


def build_combined_timeline(q: Session, user_hash: str, limit: int = 30) -> List[dict]:
    """
    Build a combined timeline of completed activities and journal entries.
    
    FIX Issue #10: This ensures completed activities appear in the timeline.
    """
    if not user_hash:
        return []
    
    try:
        # Get completed activities
        completed_activities = get_completed_activities_for_timeline(q, user_hash, limit=limit)
        
        # Get journal entries
        journal_entries = get_journal_entries_for_timeline(q, user_hash, limit=limit)
        
        # Combine and sort by date (most recent first)
        combined = []
        
        # Add completed activities (avoiding duplicates if they have journal entries)
        activity_ids_in_journal = set()
        for je in journal_entries:
            if je.get("activity_id"):
                activity_ids_in_journal.add(je["activity_id"])
        
        for ca in completed_activities:
            # Skip if this activity already has a journal entry
            if ca.get("activity_id") not in activity_ids_in_journal:
                combined.append(ca)
        
        # Add all journal entries
        combined.extend(journal_entries)
        
        # Sort by created_at (most recent first)
        def get_sort_key(item):
            created_at = item.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    return created_at
                except Exception:
                    pass
            return datetime.min
        
        combined.sort(key=get_sort_key, reverse=True)
        
        # Limit to requested number
        return combined[:limit]
        
    except Exception as e:
        print(f"[today.py] Error building combined timeline: {e}")
        return []


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
        
        # =============================================================================
        # FIX Issue #10: Build timeline with completed activities
        # =============================================================================
        timeline = build_combined_timeline(q, user_hash, limit=30)
        
        # Add stats and timeline to the summary response
        # Handle different response types from narrative.build_today_summary
        
        if hasattr(summary, 'model_dump'):
            # Pydantic v2 model - convert to dict, modify, return
            summary_dict = summary.model_dump()
            summary_dict['stats'] = stats_obj.model_dump()
            summary_dict['timeline'] = timeline
            return summary_dict
            
        elif hasattr(summary, 'dict'):
            # Pydantic v1 model - convert to dict, modify, return
            summary_dict = summary.dict()
            summary_dict['stats'] = stats_obj.dict()
            summary_dict['timeline'] = timeline
            return summary_dict
            
        elif isinstance(summary, dict):
            # Dict response
            summary['stats'] = stats_obj.dict() if hasattr(stats_obj, 'dict') else {
                'day_streak': day_streak,
                'activities_completed': activities_completed
            }
            summary['timeline'] = timeline
            return summary
            
        else:
            # Try to set stats and timeline attributes directly
            try:
                summary.stats = stats_obj
                summary.timeline = timeline
            except AttributeError:
                print("[today.py] Could not set stats/timeline on summary object")
            
    except Exception as e:
        print(f"[today.py] Error adding stats/timeline to summary: {e}")
    
    return summary


# =============================================================================
# FIX Issue #10: New endpoint to get timeline entries directly
# =============================================================================

@r.get("/api/today/timeline")
def get_timeline(
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
    limit: int = 30,
):
    """
    Get the user's timeline entries (completed activities + journal entries).
    
    FIX Issue #10: This endpoint returns completed activities in the timeline
    so they appear on the Timeline screen.
    """
    user_hash = current_user.user_hash
    
    timeline = build_combined_timeline(q, user_hash, limit=limit)
    
    # Also get stats
    day_streak = calculate_day_streak(q, user_hash)
    activities_completed = calculate_activities_completed(q, user_hash)
    
    return {
        "timeline": timeline,
        "stats": {
            "day_streak": day_streak,
            "activities_completed": activities_completed,
        },
        "count": len(timeline),
    }


# =============================================================================
# FIX Issue #10: New endpoint to get stats only
# =============================================================================

@r.get("/api/today/stats")
def get_stats(
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    """
    Get the user's stats (day streak and activities completed).
    
    This is a lightweight endpoint for just getting stats without
    the full today summary.
    """
    user_hash = current_user.user_hash
    
    day_streak = calculate_day_streak(q, user_hash)
    activities_completed = calculate_activities_completed(q, user_hash)
    
    return {
        "day_streak": day_streak,
        "activities_completed": activities_completed,
    }
