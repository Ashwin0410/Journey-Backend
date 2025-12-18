"""
Patient Analytics Service

Provides analytics and insights for therapist dashboard:
- Activity heatmaps
- Engagement metrics
- Trend analysis
- Pattern detection
"""

from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app import models


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ActivityDay:
    """Activity data for a single day."""
    date: date
    level: int  # 0-3 (none, low, medium, high)
    activity_count: int
    is_today: bool = False


@dataclass
class ActivityHeatmap:
    """Two-week activity heatmap data."""
    days: List[ActivityDay]
    total_activities: int
    period_start: date
    period_end: date


@dataclass
class EngagementMetrics:
    """Patient engagement metrics."""
    activities_this_week: int
    activities_last_week: int
    activity_trend: str  # "up", "down", "stable"
    activity_change_percent: float
    
    sessions_this_week: int
    sessions_last_week: int
    session_trend: str
    
    journals_this_week: int
    journals_last_week: int
    journal_trend: str
    
    streak_days: int
    longest_streak: int
    
    last_active: Optional[datetime]
    days_since_active: Optional[int]


@dataclass
class PatternInsight:
    """Detected pattern or insight about patient behavior."""
    pattern_type: str  # "avoidance", "improvement", "decline", "milestone", "risk"
    title: str
    description: str
    severity: str  # "info", "positive", "warning", "urgent"
    data: Dict[str, Any]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _count_in_period(
    db: Session,
    model,
    user_hash: str,
    date_field,
    start: datetime,
    end: datetime,
    extra_filters: List = None,
) -> int:
    """Count records in a date range."""
    query = db.query(func.count(model.id)).filter(
        model.user_hash == user_hash,
        date_field >= start,
        date_field < end,
    )
    
    if extra_filters:
        for f in extra_filters:
            query = query.filter(f)
    
    return query.scalar() or 0


def _get_trend(current: int, previous: int) -> str:
    """Determine trend direction."""
    if previous == 0:
        return "stable" if current == 0 else "up"
    
    change = (current - previous) / previous
    
    if change > 0.1:
        return "up"
    elif change < -0.1:
        return "down"
    else:
        return "stable"


def _calculate_change_percent(current: int, previous: int) -> float:
    """Calculate percentage change."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    
    return round(((current - previous) / previous) * 100, 1)


# =============================================================================
# ACTIVITY HEATMAP
# =============================================================================


def get_activity_heatmap(
    db: Session,
    user_hash: str,
    days: int = 14,
) -> ActivityHeatmap:
    """
    Generate activity heatmap data for the specified period.
    
    Args:
        db: Database session
        user_hash: Patient's user hash
        days: Number of days to include (default 14)
    
    Returns:
        ActivityHeatmap with daily activity levels
    """
    today = date.today()
    period_start = today - timedelta(days=days - 1)
    
    heatmap_days = []
    total_activities = 0
    
    for i in range(days):
        check_date = period_start + timedelta(days=i)
        
        # Count completed activities on this date
        activity_count = (
            db.query(func.count(models.ActivitySessions.id))
            .filter(
                models.ActivitySessions.user_hash == user_hash,
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
        
        heatmap_days.append(ActivityDay(
            date=check_date,
            level=level,
            activity_count=activity_count,
            is_today=(check_date == today),
        ))
    
    return ActivityHeatmap(
        days=heatmap_days,
        total_activities=total_activities,
        period_start=period_start,
        period_end=today,
    )


# =============================================================================
# ENGAGEMENT METRICS
# =============================================================================


def get_engagement_metrics(
    db: Session,
    user_hash: str,
) -> EngagementMetrics:
    """
    Calculate comprehensive engagement metrics for a patient.
    
    Args:
        db: Database session
        user_hash: Patient's user hash
    
    Returns:
        EngagementMetrics with all engagement data
    """
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    
    # Activities
    activities_this_week = _count_in_period(
        db, models.ActivitySessions, user_hash,
        models.ActivitySessions.completed_at,
        week_ago, now,
        [models.ActivitySessions.status == "completed"]
    )
    
    activities_last_week = _count_in_period(
        db, models.ActivitySessions, user_hash,
        models.ActivitySessions.completed_at,
        two_weeks_ago, week_ago,
        [models.ActivitySessions.status == "completed"]
    )
    
    # Sessions (audio journeys)
    sessions_this_week = (
        db.query(func.count(models.Sessions.id))
        .filter(
            models.Sessions.user_hash == user_hash,
            models.Sessions.created_at >= week_ago,
            models.Sessions.created_at < now,
        )
        .scalar()
    ) or 0
    
    sessions_last_week = (
        db.query(func.count(models.Sessions.id))
        .filter(
            models.Sessions.user_hash == user_hash,
            models.Sessions.created_at >= two_weeks_ago,
            models.Sessions.created_at < week_ago,
        )
        .scalar()
    ) or 0
    
    # Journals
    journals_this_week = _count_in_period(
        db, models.JournalEntries, user_hash,
        models.JournalEntries.created_at,
        week_ago, now,
    )
    
    journals_last_week = _count_in_period(
        db, models.JournalEntries, user_hash,
        models.JournalEntries.created_at,
        two_weeks_ago, week_ago,
    )
    
    # Streak calculation
    streak_days = _calculate_current_streak(db, user_hash)
    longest_streak = _calculate_longest_streak(db, user_hash)
    
    # Last active
    last_active = _get_last_active_datetime(db, user_hash)
    days_since_active = None
    if last_active:
        days_since_active = (now - last_active).days
    
    return EngagementMetrics(
        activities_this_week=activities_this_week,
        activities_last_week=activities_last_week,
        activity_trend=_get_trend(activities_this_week, activities_last_week),
        activity_change_percent=_calculate_change_percent(activities_this_week, activities_last_week),
        
        sessions_this_week=sessions_this_week,
        sessions_last_week=sessions_last_week,
        session_trend=_get_trend(sessions_this_week, sessions_last_week),
        
        journals_this_week=journals_this_week,
        journals_last_week=journals_last_week,
        journal_trend=_get_trend(journals_this_week, journals_last_week),
        
        streak_days=streak_days,
        longest_streak=longest_streak,
        
        last_active=last_active,
        days_since_active=days_since_active,
    )


def _calculate_current_streak(db: Session, user_hash: str) -> int:
    """Calculate current consecutive days with activity."""
    today = date.today()
    streak = 0
    
    for i in range(365):  # Max 1 year lookback
        check_date = today - timedelta(days=i)
        
        has_activity = (
            db.query(models.ActivitySessions)
            .filter(
                models.ActivitySessions.user_hash == user_hash,
                models.ActivitySessions.status == "completed",
                func.date(models.ActivitySessions.completed_at) == check_date,
            )
            .first()
        ) is not None
        
        if has_activity:
            streak += 1
        elif i == 0:
            # Today has no activity yet, but don't break streak
            continue
        else:
            break
    
    return streak


def _calculate_longest_streak(db: Session, user_hash: str) -> int:
    """Calculate longest streak of consecutive days with activity."""
    # Get all activity dates
    activity_dates = (
        db.query(func.date(models.ActivitySessions.completed_at))
        .filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status == "completed",
            models.ActivitySessions.completed_at.isnot(None),
        )
        .distinct()
        .order_by(func.date(models.ActivitySessions.completed_at))
        .all()
    )
    
    if not activity_dates:
        return 0
    
    dates = sorted([d[0] for d in activity_dates if d[0]])
    
    if not dates:
        return 0
    
    longest = 1
    current = 1
    
    for i in range(1, len(dates)):
        if dates[i] - dates[i-1] == timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    
    return longest


def _get_last_active_datetime(db: Session, user_hash: str) -> Optional[datetime]:
    """Get the most recent activity timestamp."""
    # Check multiple tables
    timestamps = []
    
    # Last journal
    last_journal = (
        db.query(func.max(models.JournalEntries.created_at))
        .filter(models.JournalEntries.user_hash == user_hash)
        .scalar()
    )
    if last_journal:
        timestamps.append(last_journal)
    
    # Last activity
    last_activity = (
        db.query(func.max(models.ActivitySessions.created_at))
        .filter(models.ActivitySessions.user_hash == user_hash)
        .scalar()
    )
    if last_activity:
        timestamps.append(last_activity)
    
    # Last session
    last_session = (
        db.query(func.max(models.Sessions.created_at))
        .filter(models.Sessions.user_hash == user_hash)
        .scalar()
    )
    if last_session:
        timestamps.append(last_session)
    
    return max(timestamps) if timestamps else None


# =============================================================================
# PATTERN DETECTION
# =============================================================================


def detect_patterns(
    db: Session,
    user_hash: str,
    intake: Optional[models.ClinicalIntake] = None,
) -> List[PatternInsight]:
    """
    Detect behavioral patterns and generate insights.
    
    Args:
        db: Database session
        user_hash: Patient's user hash
        intake: Optional clinical intake for context
    
    Returns:
        List of PatternInsight objects
    """
    patterns = []
    
    metrics = get_engagement_metrics(db, user_hash)
    
    # Pattern 1: Inactivity warning
    if metrics.days_since_active is not None and metrics.days_since_active >= 3:
        patterns.append(PatternInsight(
            pattern_type="risk",
            title="Extended Inactivity",
            description=f"No activity logged in {metrics.days_since_active} days. May need check-in.",
            severity="warning" if metrics.days_since_active < 7 else "urgent",
            data={"days_inactive": metrics.days_since_active},
        ))
    
    # Pattern 2: Activity decline
    if metrics.activity_trend == "down" and metrics.activities_last_week >= 3:
        decline_pct = abs(metrics.activity_change_percent)
        patterns.append(PatternInsight(
            pattern_type="decline",
            title="Activity Decline",
            description=f"Activity dropped {decline_pct:.0f}% from last week. Pattern suggests possible avoidance cycle.",
            severity="warning" if decline_pct > 50 else "info",
            data={
                "current": metrics.activities_this_week,
                "previous": metrics.activities_last_week,
                "change_percent": metrics.activity_change_percent,
            },
        ))
    
    # Pattern 3: Positive momentum
    if metrics.activity_trend == "up" and metrics.activities_this_week >= 5:
        patterns.append(PatternInsight(
            pattern_type="improvement",
            title="Positive Momentum",
            description=f"Activity increased {metrics.activity_change_percent:.0f}%. Great progress!",
            severity="positive",
            data={
                "current": metrics.activities_this_week,
                "previous": metrics.activities_last_week,
            },
        ))
    
    # Pattern 4: Strong streak
    if metrics.streak_days >= 5:
        patterns.append(PatternInsight(
            pattern_type="milestone",
            title="Activity Streak",
            description=f"On a {metrics.streak_days}-day streak! Consistent engagement showing strong progress.",
            severity="positive",
            data={"streak_days": metrics.streak_days},
        ))
    
    # Pattern 5: Life area avoidance (if intake available)
    if intake and intake.life_area:
        target_area = intake.life_area.lower()
        
        # Get activity distribution by life area
        week_ago = datetime.utcnow() - timedelta(days=7)
        area_activities = (
            db.query(models.Activities.life_area, func.count(models.ActivitySessions.id))
            .join(models.Activities, models.Activities.id == models.ActivitySessions.activity_id)
            .filter(
                models.ActivitySessions.user_hash == user_hash,
                models.ActivitySessions.status == "completed",
                models.ActivitySessions.completed_at >= week_ago,
            )
            .group_by(models.Activities.life_area)
            .all()
        )
        
        area_counts = {area.lower(): count for area, count in area_activities if area}
        
        if target_area not in area_counts or area_counts.get(target_area, 0) == 0:
            total = sum(area_counts.values())
            if total >= 3:  # Only flag if they're doing other activities
                patterns.append(PatternInsight(
                    pattern_type="avoidance",
                    title="Life Area Avoidance",
                    description=f"No activities logged in '{intake.life_area}' (stated focus area) this week, despite {total} activities in other areas.",
                    severity="warning",
                    data={
                        "target_area": intake.life_area,
                        "area_distribution": area_counts,
                    },
                ))
    
    # Pattern 6: First social activity
    social_count = (
        db.query(func.count(models.ActivitySessions.id))
        .join(models.Activities, models.Activities.id == models.ActivitySessions.activity_id)
        .filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status == "completed",
            models.Activities.life_area.ilike("%social%"),
        )
        .scalar()
    ) or 0
    
    if social_count == 1:
        # Check if it was recent
        latest_social = (
            db.query(models.ActivitySessions)
            .join(models.Activities, models.Activities.id == models.ActivitySessions.activity_id)
            .filter(
                models.ActivitySessions.user_hash == user_hash,
                models.ActivitySessions.status == "completed",
                models.Activities.life_area.ilike("%social%"),
            )
            .order_by(models.ActivitySessions.completed_at.desc())
            .first()
        )
        
        if latest_social and latest_social.completed_at:
            days_ago = (datetime.utcnow() - latest_social.completed_at).days
            if days_ago <= 7:
                patterns.append(PatternInsight(
                    pattern_type="milestone",
                    title="First Social Activity",
                    description="Completed first social activity! This is a significant step forward.",
                    severity="positive",
                    data={"days_ago": days_ago},
                ))
    
    return patterns


# =============================================================================
# WEEKLY SUMMARY GENERATION
# =============================================================================


def generate_weekly_summary(
    db: Session,
    user_hash: str,
    patient_name: str,
    intake: Optional[models.ClinicalIntake] = None,
) -> Dict[str, str]:
    """
    Generate AI-style weekly summary text.
    
    Args:
        db: Database session
        user_hash: Patient's user hash
        patient_name: Patient's first name
        intake: Optional clinical intake
    
    Returns:
        Dict with 'weekly_summary', 'whats_working', 'focus_areas'
    """
    metrics = get_engagement_metrics(db, user_hash)
    patterns = detect_patterns(db, user_hash, intake)
    
    # Build weekly summary
    summary_parts = []
    
    if metrics.activity_trend == "up":
        summary_parts.append(
            f"{patient_name} completed {metrics.activities_this_week} activities this week, "
            f"up from {metrics.activities_last_week} last week."
        )
    elif metrics.activity_trend == "down":
        summary_parts.append(
            f"{patient_name} completed {metrics.activities_this_week} activities this week, "
            f"down from {metrics.activities_last_week} last week."
        )
    else:
        summary_parts.append(
            f"{patient_name} completed {metrics.activities_this_week} activities this week."
        )
    
    # Add session info
    if metrics.sessions_this_week > 0:
        summary_parts.append(f"Engaged with {metrics.sessions_this_week} audio session(s).")
    
    # Add journal info
    if metrics.journals_this_week > 0:
        summary_parts.append(f"Wrote {metrics.journals_this_week} journal reflection(s).")
    
    weekly_summary = " ".join(summary_parts)
    
    # Build what's working
    working_parts = []
    
    if metrics.streak_days >= 3:
        working_parts.append(f"Maintaining a {metrics.streak_days}-day activity streak.")
    
    if metrics.activity_trend == "up":
        working_parts.append("Activity levels are increasing.")
    
    if metrics.journals_this_week >= metrics.journals_last_week and metrics.journals_this_week > 0:
        working_parts.append("Consistent journaling practice.")
    
    if not working_parts:
        working_parts.append("Building foundation with initial engagement.")
    
    whats_working = " ".join(working_parts)
    
    # Build focus areas
    focus_parts = []
    
    for pattern in patterns:
        if pattern.severity in ["warning", "urgent"]:
            focus_parts.append(pattern.description)
    
    if not focus_parts:
        focus_parts.append("Maintain current momentum and consider gradual activity increases.")
    
    focus_areas = " ".join(focus_parts[:2])  # Limit to 2 focus areas
    
    return {
        "weekly_summary": weekly_summary,
        "whats_working": whats_working,
        "focus_areas": focus_areas,
    }


# =============================================================================
# JOURNAL ANALYSIS
# =============================================================================


def get_notable_journal_entry(
    db: Session,
    user_hash: str,
    days: int = 14,
) -> Tuple[Optional[str], Optional[date]]:
    """
    Get a notable journal quote for therapist review.
    
    Prioritizes entries with emotional content or significant length.
    
    Args:
        db: Database session
        user_hash: Patient's user hash
        days: Lookback period
    
    Returns:
        Tuple of (quote text, entry date) or (None, None)
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Look for journal/reflection entries
    entries = (
        db.query(models.JournalEntries)
        .filter(
            models.JournalEntries.user_hash == user_hash,
            models.JournalEntries.entry_type.in_(["journal", "reflection"]),
            models.JournalEntries.body.isnot(None),
            func.length(models.JournalEntries.body) > 20,
            models.JournalEntries.created_at >= cutoff,
        )
        .order_by(models.JournalEntries.created_at.desc())
        .limit(10)
        .all()
    )
    
    if not entries:
        return None, None
    
    # Score entries by emotional content and length
    emotional_words = [
        "feel", "felt", "feeling", "afraid", "scared", "anxious", "worry",
        "sad", "happy", "angry", "frustrated", "hopeful", "proud", "ashamed",
        "guilty", "lonely", "grateful", "confused", "overwhelmed", "better",
        "worse", "hard", "difficult", "struggle", "help", "support"
    ]
    
    def score_entry(entry):
        body_lower = entry.body.lower()
        emotional_score = sum(1 for word in emotional_words if word in body_lower)
        length_score = min(len(entry.body) / 100, 3)  # Max 3 points for length
        recency_score = 1 if (datetime.utcnow() - entry.created_at).days <= 3 else 0
        return emotional_score + length_score + recency_score
    
    # Sort by score
    scored = sorted(entries, key=score_entry, reverse=True)
    best = scored[0]
    
    # Truncate if too long
    quote = best.body
    if len(quote) > 200:
        # Try to truncate at a sentence boundary
        truncated = quote[:200]
        last_period = truncated.rfind(".")
        if last_period > 100:
            quote = truncated[:last_period + 1]
        else:
            quote = truncated.rstrip() + "..."
    
    return quote, best.date
