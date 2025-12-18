"""
Therapist Summary Service

Generates AI-powered summaries and insights for therapist dashboard:
- Weekly patient summaries
- What's working analysis
- Focus area recommendations
- Clinical insights from patient data
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.services.patient_analytics import (
    get_engagement_metrics,
    detect_patterns,
    get_notable_journal_entry,
    get_activity_heatmap,
)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class PatientSummary:
    """Complete AI-generated summary for a patient."""
    weekly_summary: str
    whats_working: str
    focus_areas: str
    journal_insight: Optional[str]
    journal_insight_date: Optional[date]
    generated_at: datetime
    
    # Additional context
    activity_trend: str
    engagement_score: int  # 0-100
    risk_level: str  # "low", "medium", "high"
    milestones: List[str]


@dataclass
class SessionPrepNotes:
    """Notes to help therapist prepare for upcoming session."""
    key_observations: List[str]
    suggested_topics: List[str]
    progress_since_last: str
    areas_of_concern: List[str]
    positive_highlights: List[str]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_life_area_distribution(
    db: Session,
    user_hash: str,
    days: int = 7,
) -> Dict[str, int]:
    """Get distribution of activities by life area."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    results = (
        db.query(models.Activities.life_area, func.count(models.ActivitySessions.id))
        .join(models.Activities, models.Activities.id == models.ActivitySessions.activity_id)
        .filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status == "completed",
            models.ActivitySessions.completed_at >= cutoff,
        )
        .group_by(models.Activities.life_area)
        .all()
    )
    
    return {area: count for area, count in results if area}


def _get_recent_feedback_insights(
    db: Session,
    user_hash: str,
    days: int = 14,
) -> Dict[str, Any]:
    """Extract insights from recent session feedback."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    feedbacks = (
        db.query(models.Feedback)
        .join(models.Sessions, models.Sessions.id == models.Feedback.session_id)
        .filter(
            models.Sessions.user_hash == user_hash,
            models.Feedback.created_at >= cutoff,
        )
        .order_by(models.Feedback.created_at.desc())
        .limit(5)
        .all()
    )
    
    if not feedbacks:
        return {
            "avg_chills": None,
            "avg_relevance": None,
            "common_emotions": [],
            "insights": [],
        }
    
    # Calculate averages
    chills_scores = [f.chills for f in feedbacks if f.chills is not None]
    relevance_scores = [f.relevance for f in feedbacks if f.relevance is not None]
    
    avg_chills = sum(chills_scores) / len(chills_scores) if chills_scores else None
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else None
    
    # Collect emotion words
    emotions = [f.emotion_word for f in feedbacks if f.emotion_word]
    
    # Collect session insights
    insights = [f.session_insight for f in feedbacks if f.session_insight]
    
    return {
        "avg_chills": round(avg_chills, 1) if avg_chills else None,
        "avg_relevance": round(avg_relevance, 1) if avg_relevance else None,
        "common_emotions": emotions[:5],
        "insights": insights[:3],
    }


def _get_schema_context(
    db: Session,
    user_hash: str,
) -> Dict[str, Any]:
    """Get schema therapy context from clinical intake."""
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    if not intake:
        return {
            "life_area": None,
            "life_focus": None,
            "good_life_answer": None,
            "top_schemas": [],
            "phq9_total": None,
            "phq9_severity": None,
        }
    
    # Get top schemas
    schema_items = (
        db.query(models.SchemaItemResponse)
        .filter(models.SchemaItemResponse.intake_id == intake.id)
        .order_by(models.SchemaItemResponse.score.desc())
        .limit(3)
        .all()
    )
    
    top_schemas = [
        {"key": s.schema_key, "score": s.score, "prompt": s.prompt}
        for s in schema_items
    ]
    
    # Calculate PHQ-9 total
    phq9_total = (
        db.query(func.sum(models.Phq9ItemResponse.score))
        .filter(models.Phq9ItemResponse.intake_id == intake.id)
        .scalar()
    )
    
    # Determine severity
    phq9_severity = None
    if phq9_total is not None:
        if phq9_total <= 4:
            phq9_severity = "minimal"
        elif phq9_total <= 9:
            phq9_severity = "mild"
        elif phq9_total <= 14:
            phq9_severity = "moderate"
        elif phq9_total <= 19:
            phq9_severity = "moderately severe"
        else:
            phq9_severity = "severe"
    
    return {
        "life_area": intake.life_area,
        "life_focus": intake.life_focus,
        "good_life_answer": intake.good_life_answer,
        "top_schemas": top_schemas,
        "phq9_total": phq9_total,
        "phq9_severity": phq9_severity,
        "pre_intake_text": intake.pre_intake_text,
    }


def _calculate_engagement_score(metrics) -> int:
    """Calculate an overall engagement score (0-100)."""
    score = 0
    
    # Activity component (0-40 points)
    if metrics.activities_this_week >= 7:
        score += 40
    elif metrics.activities_this_week >= 5:
        score += 30
    elif metrics.activities_this_week >= 3:
        score += 20
    elif metrics.activities_this_week >= 1:
        score += 10
    
    # Streak component (0-20 points)
    if metrics.streak_days >= 7:
        score += 20
    elif metrics.streak_days >= 5:
        score += 15
    elif metrics.streak_days >= 3:
        score += 10
    elif metrics.streak_days >= 1:
        score += 5
    
    # Session component (0-20 points)
    if metrics.sessions_this_week >= 3:
        score += 20
    elif metrics.sessions_this_week >= 2:
        score += 15
    elif metrics.sessions_this_week >= 1:
        score += 10
    
    # Journal component (0-20 points)
    if metrics.journals_this_week >= 5:
        score += 20
    elif metrics.journals_this_week >= 3:
        score += 15
    elif metrics.journals_this_week >= 1:
        score += 10
    
    return min(score, 100)


def _determine_risk_level(
    metrics,
    patterns: List,
    schema_context: Dict,
) -> str:
    """Determine overall risk level for the patient."""
    risk_score = 0
    
    # Inactivity risk
    if metrics.days_since_active is not None:
        if metrics.days_since_active >= 7:
            risk_score += 3
        elif metrics.days_since_active >= 3:
            risk_score += 2
        elif metrics.days_since_active >= 2:
            risk_score += 1
    
    # Activity decline risk
    if metrics.activity_trend == "down":
        if metrics.activity_change_percent <= -50:
            risk_score += 2
        else:
            risk_score += 1
    
    # PHQ-9 risk
    phq9_total = schema_context.get("phq9_total")
    if phq9_total is not None:
        if phq9_total >= 20:
            risk_score += 3
        elif phq9_total >= 15:
            risk_score += 2
        elif phq9_total >= 10:
            risk_score += 1
    
    # Pattern-based risk
    for pattern in patterns:
        if pattern.severity == "urgent":
            risk_score += 2
        elif pattern.severity == "warning":
            risk_score += 1
    
    # Determine level
    if risk_score >= 5:
        return "high"
    elif risk_score >= 2:
        return "medium"
    else:
        return "low"


# =============================================================================
# MAIN SUMMARY GENERATION
# =============================================================================


def generate_patient_summary(
    db: Session,
    user_hash: str,
    patient_name: Optional[str] = None,
) -> PatientSummary:
    """
    Generate a comprehensive AI-style summary for a patient.
    
    This is the main function called by the dashboard API.
    
    Args:
        db: Database session
        user_hash: Patient's user hash
        patient_name: Patient's name for personalization
    
    Returns:
        PatientSummary with all summary components
    """
    # Get all the data we need
    metrics = get_engagement_metrics(db, user_hash)
    
    # Get intake for context
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    patterns = detect_patterns(db, user_hash, intake)
    schema_context = _get_schema_context(db, user_hash)
    life_areas = _get_life_area_distribution(db, user_hash, days=7)
    feedback_insights = _get_recent_feedback_insights(db, user_hash)
    journal_quote, journal_date = get_notable_journal_entry(db, user_hash)
    
    # Use first name or "Patient"
    first_name = patient_name.split()[0] if patient_name else "Patient"
    
    # =========================
    # BUILD WEEKLY SUMMARY
    # =========================
    
    summary_parts = []
    
    # Activity summary
    if metrics.activity_trend == "up":
        summary_parts.append(
            f"{first_name} completed {metrics.activities_this_week} activities this week, "
            f"up from {metrics.activities_last_week} last week."
        )
    elif metrics.activity_trend == "down" and metrics.activities_last_week > 0:
        summary_parts.append(
            f"{first_name} completed {metrics.activities_this_week} activities this week, "
            f"down from {metrics.activities_last_week} last week."
        )
        
        # Add context about when activity dropped
        if metrics.activities_this_week < metrics.activities_last_week * 0.5:
            summary_parts.append(
                "Activity dropped significantly mid-week."
            )
    else:
        summary_parts.append(
            f"{first_name} completed {metrics.activities_this_week} activities this week."
        )
    
    # Life area distribution
    if life_areas:
        top_area = max(life_areas, key=life_areas.get) if life_areas else None
        
        # Check for avoidance of target area
        target_area = schema_context.get("life_area")
        if target_area:
            target_lower = target_area.lower()
            area_lower_map = {k.lower(): k for k in life_areas}
            
            if target_lower not in area_lower_map:
                summary_parts.append(
                    f"Avoiding {target_area.lower()} activities but maintained "
                    f"{top_area.lower()}-based ones."
                )
            elif top_area and top_area.lower() != target_lower:
                summary_parts.append(
                    f"Most active in {top_area.lower()} activities."
                )
    
    # Journal correlation
    if metrics.journals_this_week > 0 and metrics.activity_trend == "down":
        summary_parts.append(
            "Journaling suggests awareness of the dip."
        )
    
    weekly_summary = " ".join(summary_parts)
    
    # =========================
    # BUILD WHAT'S WORKING
    # =========================
    
    working_parts = []
    
    # Consistent activities
    if life_areas:
        consistent_areas = [area for area, count in life_areas.items() if count >= 3]
        if consistent_areas:
            working_parts.append(
                f"{consistent_areas[0]} activities remain consistent."
            )
    
    # Positive feedback from sessions
    if feedback_insights.get("avg_relevance") and feedback_insights["avg_relevance"] >= 4:
        working_parts.append(
            "Audio sessions are resonating well (high relevance scores)."
        )
    
    # Chills/emotional connection
    if feedback_insights.get("avg_chills") and feedback_insights["avg_chills"] >= 2:
        working_parts.append(
            "Experiencing emotional connection during sessions."
        )
    
    # Journal insights
    if feedback_insights.get("insights"):
        working_parts.append(
            "Showing self-awareness in session reflections."
        )
    
    # Streak
    if metrics.streak_days >= 3:
        working_parts.append(
            f"Maintained a {metrics.streak_days}-day activity streak."
        )
    
    # Positive patterns
    positive_patterns = [p for p in patterns if p.severity == "positive"]
    for pattern in positive_patterns[:1]:
        working_parts.append(pattern.description)
    
    # Default if nothing else
    if not working_parts:
        working_parts.append(
            "Building foundation with initial activities. "
            "Connection between action and mood improvement becoming clearer."
        )
    
    whats_working = " ".join(working_parts)
    
    # =========================
    # BUILD FOCUS AREAS
    # =========================
    
    focus_parts = []
    
    # Warning/urgent patterns first
    concern_patterns = [p for p in patterns if p.severity in ["warning", "urgent"]]
    for pattern in concern_patterns[:2]:
        if pattern.pattern_type == "avoidance":
            focus_parts.append(
                f"Avoidance pattern around {schema_context.get('life_area', 'target')} activities."
            )
        elif pattern.pattern_type == "decline":
            focus_parts.append(
                "Explore what changed this week that led to activity drop."
            )
        elif pattern.pattern_type == "risk":
            focus_parts.append(pattern.description)
    
    # Schema-based suggestions
    top_schemas = schema_context.get("top_schemas", [])
    if top_schemas and top_schemas[0].get("score", 0) >= 4:
        schema_key = top_schemas[0].get("key", "")
        if schema_key:
            focus_parts.append(
                f"High '{schema_key}' schema may be influencing avoidance patterns."
            )
    
    # Social connection if relevant
    social_count = life_areas.get("Social", 0) + life_areas.get("social", 0) + life_areas.get("Connection", 0)
    if social_count == 0 and metrics.activities_this_week >= 3:
        focus_parts.append(
            "Consider introducing gentle social activities."
        )
    
    # Default if nothing concerning
    if not focus_parts:
        focus_parts.append(
            "Maintain current momentum. Consider gradually increasing activity challenge level."
        )
    
    focus_areas = " ".join(focus_parts[:2])  # Limit to 2 focus areas
    
    # =========================
    # CALCULATE SCORES & LEVELS
    # =========================
    
    engagement_score = _calculate_engagement_score(metrics)
    risk_level = _determine_risk_level(metrics, patterns, schema_context)
    
    # Extract milestones
    milestones = [
        p.title for p in patterns 
        if p.pattern_type == "milestone" and p.severity == "positive"
    ]
    
    return PatientSummary(
        weekly_summary=weekly_summary,
        whats_working=whats_working,
        focus_areas=focus_areas,
        journal_insight=journal_quote,
        journal_insight_date=journal_date,
        generated_at=datetime.utcnow(),
        activity_trend=metrics.activity_trend,
        engagement_score=engagement_score,
        risk_level=risk_level,
        milestones=milestones,
    )


# =============================================================================
# SESSION PREP NOTES
# =============================================================================


def generate_session_prep_notes(
    db: Session,
    user_hash: str,
    patient_name: Optional[str] = None,
    last_session_date: Optional[date] = None,
) -> SessionPrepNotes:
    """
    Generate notes to help therapist prepare for upcoming session.
    
    Args:
        db: Database session
        user_hash: Patient's user hash
        patient_name: Patient's name
        last_session_date: Date of last in-person session
    
    Returns:
        SessionPrepNotes with preparation content
    """
    # Get summary data
    summary = generate_patient_summary(db, user_hash, patient_name)
    metrics = get_engagement_metrics(db, user_hash)
    schema_context = _get_schema_context(db, user_hash)
    feedback_insights = _get_recent_feedback_insights(db, user_hash)
    
    first_name = patient_name.split()[0] if patient_name else "Patient"
    
    # =========================
    # KEY OBSERVATIONS
    # =========================
    
    observations = []
    
    # Activity trend
    if metrics.activity_trend == "up":
        observations.append(
            f"Activity increased {abs(metrics.activity_change_percent):.0f}% this week"
        )
    elif metrics.activity_trend == "down":
        observations.append(
            f"Activity decreased {abs(metrics.activity_change_percent):.0f}% this week"
        )
    
    # Engagement
    if summary.engagement_score >= 70:
        observations.append("High overall engagement with the app")
    elif summary.engagement_score <= 30:
        observations.append("Low app engagement - may need motivation discussion")
    
    # Streak
    if metrics.streak_days >= 5:
        observations.append(f"On a {metrics.streak_days}-day activity streak")
    
    # Risk level
    if summary.risk_level == "high":
        observations.append("⚠️ Elevated risk indicators detected")
    
    # PHQ-9
    if schema_context.get("phq9_severity") in ["moderately severe", "severe"]:
        observations.append(
            f"PHQ-9 indicates {schema_context['phq9_severity']} depression "
            f"(score: {schema_context['phq9_total']})"
        )
    
    # =========================
    # SUGGESTED TOPICS
    # =========================
    
    topics = []
    
    # Based on patterns
    if summary.risk_level != "low":
        topics.append("Check in on mood and any concerning thoughts")
    
    if metrics.activity_trend == "down":
        topics.append("Explore barriers to activity completion")
    
    if schema_context.get("life_area"):
        life_areas = _get_life_area_distribution(db, user_hash)
        target = schema_context["life_area"]
        if target.lower() not in [a.lower() for a in life_areas]:
            topics.append(f"Discuss avoidance of {target.lower()} activities")
    
    # Positive topics
    if summary.milestones:
        topics.append(f"Celebrate milestone: {summary.milestones[0]}")
    
    if metrics.streak_days >= 3:
        topics.append("Reinforce the habit-building success")
    
    # Schema work
    top_schemas = schema_context.get("top_schemas", [])
    if top_schemas:
        topics.append(f"Continue work on '{top_schemas[0].get('key')}' schema")
    
    # Default
    if not topics:
        topics.append("Review week's activities and emotional responses")
        topics.append("Plan next week's behavioral goals")
    
    # =========================
    # PROGRESS SINCE LAST
    # =========================
    
    if last_session_date:
        days_since = (date.today() - last_session_date).days
        
        # Count activities since last session
        activities_since = (
            db.query(func.count(models.ActivitySessions.id))
            .filter(
                models.ActivitySessions.user_hash == user_hash,
                models.ActivitySessions.status == "completed",
                func.date(models.ActivitySessions.completed_at) >= last_session_date,
            )
            .scalar()
        ) or 0
        
        progress = (
            f"In the {days_since} days since last session, {first_name} completed "
            f"{activities_since} activities. "
        )
        
        if metrics.activity_trend == "up":
            progress += "Overall trend is positive."
        elif metrics.activity_trend == "down":
            progress += "Activity has declined - worth exploring."
        else:
            progress += "Maintaining steady engagement."
    else:
        progress = "No previous session date recorded."
    
    # =========================
    # AREAS OF CONCERN
    # =========================
    
    concerns = []
    
    if summary.risk_level == "high":
        concerns.append("Multiple risk indicators present")
    
    if metrics.days_since_active and metrics.days_since_active >= 3:
        concerns.append(f"No activity in {metrics.days_since_active} days")
    
    if schema_context.get("phq9_total") and schema_context["phq9_total"] >= 15:
        concerns.append("Elevated depression severity")
    
    if metrics.activity_change_percent <= -50 and metrics.activities_last_week >= 3:
        concerns.append("Significant activity drop (>50%)")
    
    # =========================
    # POSITIVE HIGHLIGHTS
    # =========================
    
    highlights = []
    
    for milestone in summary.milestones:
        highlights.append(milestone)
    
    if metrics.streak_days >= 3:
        highlights.append(f"{metrics.streak_days}-day activity streak")
    
    if metrics.activity_trend == "up":
        highlights.append("Increasing activity engagement")
    
    if feedback_insights.get("avg_relevance") and feedback_insights["avg_relevance"] >= 4:
        highlights.append("Finding audio sessions helpful")
    
    if metrics.journals_this_week >= 3:
        highlights.append("Active journaling practice")
    
    return SessionPrepNotes(
        key_observations=observations,
        suggested_topics=topics[:5],  # Limit to 5 topics
        progress_since_last=progress,
        areas_of_concern=concerns,
        positive_highlights=highlights,
    )


# =============================================================================
# ATTENTION DETECTION
# =============================================================================


def check_needs_attention(
    db: Session,
    user_hash: str,
) -> Tuple[bool, str, str]:
    """
    Quick check if patient needs attention.
    
    Returns:
        Tuple of (needs_attention: bool, attention_type: str, reason: str)
    """
    metrics = get_engagement_metrics(db, user_hash)
    schema_context = _get_schema_context(db, user_hash)
    
    # Check inactivity
    if metrics.days_since_active is not None and metrics.days_since_active >= 3:
        return (
            True,
            "inactive",
            f"No activity in {metrics.days_since_active} days"
        )
    
    # Check activity decline
    if (metrics.activities_last_week >= 3 and 
        metrics.activities_this_week < metrics.activities_last_week * 0.5):
        return (
            True,
            "low_activity",
            f"Activity dropped from {metrics.activities_last_week} to {metrics.activities_this_week}"
        )
    
    # Check PHQ-9
    phq9_total = schema_context.get("phq9_total")
    if phq9_total is not None and phq9_total >= 15:
        return (
            True,
            "high_phq9",
            f"PHQ-9 score of {phq9_total} indicates {schema_context['phq9_severity']} depression"
        )
    
    return (False, "", "")


def check_has_milestone(
    db: Session,
    user_hash: str,
) -> Tuple[bool, str, str]:
    """
    Quick check if patient has a recent milestone.
    
    Returns:
        Tuple of (has_milestone: bool, milestone_type: str, description: str)
    """
    metrics = get_engagement_metrics(db, user_hash)
    
    # Check for activity streak
    if metrics.streak_days >= 5:
        return (
            True,
            "activity_streak",
            f"On a {metrics.streak_days}-day activity streak"
        )
    
    # Check for first social activity
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
        # Verify it was recent
        latest = (
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
        
        if latest and latest.completed_at:
            days_ago = (datetime.utcnow() - latest.completed_at).days
            if days_ago <= 7:
                return (
                    True,
                    "first_social_activity",
                    "Completed first social activity"
                )
    
    # Check for significant activity increase
    if (metrics.activities_last_week >= 1 and 
        metrics.activities_this_week >= metrics.activities_last_week * 1.5 and
        metrics.activities_this_week >= 5):
        return (
            True,
            "activity_increase",
            f"Activity increased from {metrics.activities_last_week} to {metrics.activities_this_week}"
        )
    
    return (False, "", "")
