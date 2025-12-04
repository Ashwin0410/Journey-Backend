from __future__ import annotations

import math
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from .. import models, schemas

# Cooldown (in minutes) for Journey button lock
DEFAULT_JOURNEY_COOLDOWN_MINUTES = 45


def compute_journey_state(
    db: Session,
    user_hash: Optional[str],
    cooldown_minutes: int = DEFAULT_JOURNEY_COOLDOWN_MINUTES,
) -> Dict[str, Any]:
    """
    Simple rule-based state for the Journey button.

    - If no user_hash or no sessions -> ready.
    - If last session older than cooldown_minutes -> ready.
    - Else -> cooldown with remaining minutes.
    """
    if not user_hash:
        return {
            "status": "ready",
            "cooldown_minutes_remaining": 0,
            "last_session_at": None,
        }

    last = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(models.Sessions.created_at.desc())
        .first()
    )
    if not last or not last.created_at:
        return {
            "status": "ready",
            "cooldown_minutes_remaining": 0,
            "last_session_at": None,
        }

    # normalise to naive UTC for subtraction
    now = datetime.utcnow()
    last_dt = last.created_at
    if getattr(last_dt, "tzinfo", None) is not None:
        last_dt = last_dt.replace(tzinfo=None)

    elapsed_min = (now - last_dt).total_seconds() / 60.0
    if elapsed_min >= cooldown_minutes:
        return {
            "status": "ready",
            "cooldown_minutes_remaining": 0,
            "last_session_at": last_dt.isoformat(),
        }

    remaining = max(0, math.ceil(cooldown_minutes - elapsed_min))
    return {
        "status": "cooldown",
        "cooldown_minutes_remaining": int(remaining),
        "last_session_at": last_dt.isoformat(),
    }


def _time_of_day_greeting(now: Optional[datetime] = None) -> str:
    now = now or datetime.utcnow()
    h = now.hour
    if 5 <= h < 12:
        return "Good morning"
    if 12 <= h < 18:
        return "Good afternoon"
    if 18 <= h < 23:
        return "Good evening"
    return "Hey"


def _first_name(full_name: Optional[str]) -> Optional[str]:
    if not full_name:
        return None
    parts = full_name.strip().split()
    return parts[0] if parts else None


def _pick_schema_label(db: Session, user_hash: str) -> Optional[str]:
    """
    Very simple rule:
    - If we have recent Sessions with schema_hint, use that.
    - Else, look at SchemaItemResponse and pick the highest score.
    """
    last_session = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(models.Sessions.created_at.desc())
        .first()
    )
    if last_session and last_session.schema_hint:
        return last_session.schema_hint

    # fall back to intake schema items with highest score
    item = (
        db.query(models.SchemaItemResponse)
        .filter(models.SchemaItemResponse.user_hash == user_hash)
        .order_by(
            models.SchemaItemResponse.score.desc(),
            models.SchemaItemResponse.id.asc(),
        )
        .first()
    )
    if item and item.schema_key:
        return item.schema_key
    return None


def _last_session_feedback(db: Session, user_hash: str) -> Dict[str, Any]:
    """
    Return info about the most recent session + feedback for this user.
    """
    session = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(models.Sessions.created_at.desc())
        .first()
    )
    if not session:
        return {
            "has_session": False,
            "mood": None,
            "schema_hint": None,
            "feedback": None,
        }

    fb = (
        db.query(models.Feedback)
        .filter(models.Feedback.session_id == session.id)
        .order_by(models.Feedback.created_at.desc())
        .first()
    )

    feedback_obj = None
    if fb:
        feedback_obj = {
            "chills": fb.chills,
            "relevance": fb.relevance,
            "emotion_word": fb.emotion_word,
            "chills_option": fb.chills_option,
            "chills_detail": fb.chills_detail,
            "session_insight": fb.session_insight,
        }

    return {
        "has_session": True,
        "mood": session.mood,
        "schema_hint": session.schema_hint or None,
        "feedback": feedback_obj,
    }


def _build_hero_narrative(
    *,
    user_name: Optional[str],
    schema_label: Optional[str],
    mood: Optional[str],
    feedback: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Rule-based copy for the 'Hero Card' narrative on the Today screen.
    No LLMs, just templates.
    """
    name_piece = _first_name(user_name) or "you"
    schema_phrase = schema_label or "an old story about yourself"
    mood_phrase = mood or "mixed"

    base = (
        f"You’re quietly collecting evidence that you’re more than {schema_phrase}. "
        f"Even on {mood_phrase} days, the fact that {name_piece} keeps showing up "
        "is proof of agency, not failure."
    )

    if feedback:
        emotion = feedback.get("emotion_word") or "something subtle"
        chills_opt = feedback.get("chills_option")
        if chills_opt == "yes":
            chills_line = (
                f" There was a real chills moment last time – that spark of {emotion} "
                "is part of your story now, not an accident."
            )
        elif chills_opt == "subtle":
            chills_line = (
                f" Last time the shift was quieter, more like a small wave of {emotion}; "
                "those small waves still count."
            )
        else:
            chills_line = (
                " Even if nothing dramatic happened in the last session, staying with the process "
                "is already changing the shape of your days."
            )
        text = base + chills_line
    else:
        text = (
            base
            + " You’re building a track record of small, boring, solid evidence that you can move "
              "through this, one step at a time."
        )

    highlight_terms: List[str] = []
    if schema_label:
        highlight_terms.append(schema_label)
    highlight_terms.extend(["agency", "evidence", "small steps"])
    # dedupe while preserving order
    seen = set()
    highlight_terms = [t for t in highlight_terms if not (t in seen or seen.add(t))]

    return {
        "hero_narrative": text,
        "highlight_terms": highlight_terms,
    }


def _pick_recommended_activity(db: Session) -> Optional[schemas.ActivityRecommendationOut]:
    """
    For V1 (no extra LLM here):
    - Just pick the most recently created active Activity.
    - This plugs into the Smart Activity Card with minimal logic.
    """
    row = (
        db.query(models.Activities)
        .filter(models.Activities.is_active == True)
        .order_by(models.Activities.created_at.desc())
        .first()
    )
    if not row:
        return None

    tags: List[str] = []
    if row.tags_json:
        try:
            import json  # local import to avoid top-level if unused
            tags = json.loads(row.tags_json) or []
        except Exception:
            tags = []

    return schemas.ActivityRecommendationOut(
        id=row.id,
        title=row.title,
        description=row.description,
        life_area=row.life_area,
        effort_level=row.effort_level,
        reward_type=row.reward_type,
        default_duration_min=row.default_duration_min,
        location_label=row.location_label,
        tags=tags,
    )


def _extract_postal_code(db: Session, user_hash: Optional[str]) -> Optional[str]:
    """
    Try to read the latest postal_code from the user's intake.
    IMPORTANT: use models.ClinicalIntake (the model that actually exists).
    Return None safely if anything goes wrong.
    """
    if not user_hash:
        return None

    # Ensure the ORM model exists
    if not hasattr(models, "ClinicalIntake"):
        return None

    try:
        row = (
            db.query(models.ClinicalIntake)
            .filter(models.ClinicalIntake.user_hash == user_hash)
            .order_by(models.ClinicalIntake.created_at.desc())
            .first()
        )
    except Exception:
        return None

    if not row:
        return None

    return getattr(row, "postal_code", None)


def build_today_summary(db: Session, user: models.Users) -> schemas.TodaySummaryOut:
    """
    Build the full Today payload (Hero card + Journey state + one recommended activity).
    Purely rule-based; no LLM calls.
    """
    now = datetime.utcnow()
    greeting = _time_of_day_greeting(now)
    fname = _first_name(user.name)
    if fname:
        greeting = f"{greeting}, {fname}"
    else:
        greeting = f"{greeting}"

    # Last session + feedback
    session_info = _last_session_feedback(db, user.user_hash)
    schema_label = _pick_schema_label(db, user.user_hash)
    hero_bits = _build_hero_narrative(
        user_name=user.name,
        schema_label=schema_label or session_info.get("schema_hint"),
        mood=session_info.get("mood"),
        feedback=session_info.get("feedback"),
    )

    # Journey button state
    j_state = compute_journey_state(db, user.user_hash)
    journey_ready = j_state.get("status") == "ready"
    cooldown_remaining = int(j_state.get("cooldown_minutes_remaining", 0))

    # Recommended activity (simple, rule-based)
    rec_act = _pick_recommended_activity(db)

    # 🔑 Supply postal_code so the frontend can pass it to the activity
    # recommendation endpoint (and anything else that needs geo context).
    postal_code = _extract_postal_code(db, user.user_hash)

    return schemas.TodaySummaryOut(
        greeting=greeting,
        current_date=now.date(),
        journey_day=user.journey_day,
        hero_narrative=hero_bits["hero_narrative"],
        highlight_terms=hero_bits["highlight_terms"],
        has_recent_session=bool(session_info.get("has_session")),
        journey_ready=journey_ready,
        journey_cooldown_minutes_remaining=cooldown_remaining,
        recommended_activity=rec_act,
        postal_code=postal_code,
    )
