from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Date,
    Boolean,
    ForeignKey,
)
from sqlalchemy.sql import func

from .db import Base


class Sessions(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=True)
    track_id = Column(String, index=True)
    voice_id = Column(String, index=True)
    audio_path = Column(String, nullable=False)
    mood = Column(String, index=True)
    schema_hint = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    chills = Column(Integer)
    relevance = Column(Integer)
    emotion_word = Column(String)

    # NEW: align with richer post-session form
    chills_option = Column(String, nullable=True)   # "yes" | "subtle" | "no"
    chills_detail = Column(Text, nullable=True)     # "What sparked that moment?"
    session_insight = Column(Text, nullable=True)   # "Any insights from this session?"
    meta_json = Column(Text, nullable=True)         # optional future-proof field

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KV(Base):
    __tablename__ = "kv"
    k = Column(String, primary_key=True)
    v = Column(Text)


# Store full scripts keyed by session_id
class Scripts(Base):
    __tablename__ = "scripts"
    session_id = Column(String, primary_key=True, index=True)
    script_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Per-moment events during a Journey session (chills button, insights, etc.)
class JourneyEvent(Base):
    __tablename__ = "journey_events"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    user_hash = Column(String, index=True, nullable=True)
    event_type = Column(String, index=True)  # e.g. "chills", "insight", "note"
    t_ms = Column(Integer)                   # timestamp in ms within the audio
    label = Column(String, nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Activity catalogue (BA actions, e.g., walks, calls, small tasks)
class Activities(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    life_area = Column(String, index=True)          # e.g. "Social", "Body", "Work", "Meaning"
    effort_level = Column(String, index=True)       # e.g. "low", "medium", "high"
    reward_type = Column(String, index=True, nullable=True)  # e.g. "serotonin", "dopamine"
    default_duration_min = Column(Integer, nullable=True)
    location_label = Column(String, nullable=True)  # e.g. "Near your home", "Park"
    tags_json = Column(Text, nullable=True)         # JSON-encoded list of tags
    is_active = Column(Integer, default=1, index=True)  # 1 = active, 0 = disabled
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# User ↔ Activity relationship over time (suggested, started, completed, swapped)
class ActivitySessions(Base):
    __tablename__ = "activity_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True)
    activity_id = Column(Integer, index=True)
    session_id = Column(String, index=True, nullable=True)  # link to Journey session if relevant
    status = Column(String, index=True)                     # "suggested", "started", "completed", "swapped"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


# Journal + Map timeline entries
class JournalEntries(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True)
    session_id = Column(String, index=True, nullable=True)   # optional link to Journey session
    entry_type = Column(String, index=True)                  # "journal", "insight", "activity", "therapy_future"
    title = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    meta_json = Column(Text, nullable=True)                  # JSON with extra data (duration, location, etc.)
    date = Column(Date, index=True)                          # calendar date for grouping
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- Users table for Google auth + Journey streak ----
class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, unique=True, index=True, nullable=False)

    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)

    provider = Column(String, nullable=False)      # e.g. "google"
    provider_id = Column(String, nullable=False)   # Google "sub" id

    profile_json = Column(Text, nullable=True)     # raw Google payload as JSON

    # Journey streak-style progress (1, 2, 3, ...)
    journey_day = Column(Integer, nullable=True)
    last_journey_date = Column(Date, nullable=True, index=True)

    # NEW: onboarding and safety state
    onboarding_complete = Column(Boolean, default=False, nullable=False)
    safety_flag = Column(Integer, nullable=True)        # 0/1/2 style risk level
    last_phq9_date = Column(Date, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- Clinical intake & assessments ----

class ClinicalIntake(Base):
    """
    One row = one completed intake wizard for a user.

    Holds:
    - basic info
    - therapy/medication
    - safety screening flags
    - weekly plan + 90-year reflection

    Schema + PHQ-9 answers are stored in child tables.
    """
    __tablename__ = "clinical_intakes"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)

    # Basic info
    age = Column(Integer, nullable=True)
    postal_code = Column(String, nullable=True)
    gender = Column(String, nullable=True)  # "male", "female", "non_binary", etc.

    # Therapy / medication
    in_therapy = Column(Boolean, default=False)
    therapy_type = Column(Text, nullable=True)
    therapy_duration = Column(String, nullable=True)

    on_medication = Column(Boolean, default=False)
    medication_list = Column(Text, nullable=True)
    medication_duration = Column(String, nullable=True)

    # Safety screening
    pregnant_or_planning = Column(Boolean, default=False)
    pregnant_notes = Column(Text, nullable=True)
    psychosis_history = Column(Boolean, default=False)
    psychosis_notes = Column(Text, nullable=True)
    privacy_ack = Column(Boolean, default=False)

    # Weekly life-area planning
    life_area = Column(String, nullable=True)           # e.g. "Recreation / Leisure"
    life_focus = Column(String, nullable=True)          # e.g. "Learning for fun"
    week_actions_json = Column(Text, nullable=True)     # JSON list of actions
    week_plan_text = Column(Text, nullable=True)        # "Your Week Plan" sentence

    # Final 90-year-old reflection
    good_life_answer = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SchemaItemResponse(Base):
    """
    One row per schema personalization statement.
    Example schema_key: "defectiveness_shame", "failure", "emotional_deprivation", etc.
    """
    __tablename__ = "schema_item_responses"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(
        Integer,
        ForeignKey("clinical_intakes.id", ondelete="CASCADE"),
        index=True,
    )
    user_hash = Column(String, index=True, nullable=False)

    schema_key = Column(String, index=True)  # machine name, e.g. "defectiveness_shame"
    prompt = Column(Text, nullable=True)     # full text of the question (optional)
    score = Column(Integer, nullable=False)  # 1–6
    note = Column(Text, nullable=True)       # optional free text
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Phq9ItemResponse(Base):
    """
    One row per PHQ-9 question.
    """
    __tablename__ = "phq9_item_responses"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(
        Integer,
        ForeignKey("clinical_intakes.id", ondelete="CASCADE"),
        index=True,
    )
    user_hash = Column(String, index=True, nullable=False)

    question_number = Column(Integer, index=True)      # 1..9
    prompt = Column(Text, nullable=True)               # full text (optional)
    score = Column(Integer, nullable=False)            # 0..3
    note = Column(Text, nullable=True)                 # optional free text

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # denormalized helpers
    is_suicide_item = Column(Boolean, default=False)   # True only for Q9


# ---------- NEW: Mini check-ins (Day-2+ quick questionnaire) ----------
class MiniCheckins(Base):
    __tablename__ = "mini_checkins"
    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)

    feeling = Column(String, nullable=True)
    body = Column(String, nullable=True)
    energy = Column(String, nullable=True)
    goal_today = Column(String, nullable=True)
    why_goal = Column(String, nullable=True)
    last_win = Column(String, nullable=True)
    hard_thing = Column(String, nullable=True)
    schema_choice = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    place = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
