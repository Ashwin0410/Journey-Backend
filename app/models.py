from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Date,
    Boolean,
    ForeignKey,
    Float,
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

    chills_option = Column(String, nullable=True)  
    chills_detail = Column(Text, nullable=True)     
    session_insight = Column(Text, nullable=True)   
    meta_json = Column(Text, nullable=True)         

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KV(Base):
    __tablename__ = "kv"
    k = Column(String, primary_key=True)
    v = Column(Text)



class Scripts(Base):
    __tablename__ = "scripts"
    session_id = Column(String, primary_key=True, index=True)
    script_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class JourneyEvent(Base):
    __tablename__ = "journey_events"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    user_hash = Column(String, index=True, nullable=True)
    event_type = Column(String, index=True) 
    t_ms = Column(Integer)                  
    label = Column(String, nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class Activities(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    life_area = Column(String, index=True)        
    effort_level = Column(String, index=True)     
    reward_type = Column(String, index=True, nullable=True) 
    default_duration_min = Column(Integer, nullable=True)
    location_label = Column(String, nullable=True)  
    tags_json = Column(Text, nullable=True)         
    is_active = Column(Integer, default=1, index=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Google Maps coordinates for directions
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    place_id = Column(String, nullable=True)  # Google Place ID for precise directions



class ActivitySessions(Base):
    __tablename__ = "activity_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True)
    activity_id = Column(Integer, index=True)
    session_id = Column(String, index=True, nullable=True)  
    status = Column(String, index=True)                     
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)



class JournalEntries(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True)
    session_id = Column(String, index=True, nullable=True)   
    entry_type = Column(String, index=True)                  
    title = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    meta_json = Column(Text, nullable=True)                  
    date = Column(Date, index=True)                          
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, unique=True, index=True, nullable=False)

    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)

    provider = Column(String, nullable=False)    
    provider_id = Column(String, nullable=True)  # nullable for email users

    password_hash = Column(String, nullable=True)  # for email/password auth

    profile_json = Column(Text, nullable=True)   

    
    journey_day = Column(Integer, nullable=True)
    last_journey_date = Column(Date, nullable=True, index=True)

    
    onboarding_complete = Column(Boolean, default=False, nullable=False)
    safety_flag = Column(Integer, nullable=True)        # 0/1/2 style risk level
    last_phq9_date = Column(Date, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())




class ClinicalIntake(Base):

    __tablename__ = "clinical_intakes"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)

    # Pre-intake question: "Has anything been on your mind lately?"
    pre_intake_text = Column(Text, nullable=True)

    
    age = Column(Integer, nullable=True)
    postal_code = Column(String, nullable=True)
    gender = Column(String, nullable=True) 

    
    in_therapy = Column(Boolean, default=False)
    therapy_type = Column(Text, nullable=True)
    therapy_duration = Column(String, nullable=True)

    on_medication = Column(Boolean, default=False)
    medication_list = Column(Text, nullable=True)
    medication_duration = Column(String, nullable=True)

    
    pregnant_or_planning = Column(Boolean, default=False)
    pregnant_notes = Column(Text, nullable=True)
    psychosis_history = Column(Boolean, default=False)
    psychosis_notes = Column(Text, nullable=True)
    privacy_ack = Column(Boolean, default=False)

    
    life_area = Column(String, nullable=True)           
    life_focus = Column(String, nullable=True)          
    week_actions_json = Column(Text, nullable=True)     
    week_plan_text = Column(Text, nullable=True)        

    
    good_life_answer = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SchemaItemResponse(Base):
    
    __tablename__ = "schema_item_responses"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(
        Integer,
        ForeignKey("clinical_intakes.id", ondelete="CASCADE"),
        index=True,
    )
    user_hash = Column(String, index=True, nullable=False)

    schema_key = Column(String, index=True)  
    prompt = Column(Text, nullable=True)     
    score = Column(Integer, nullable=False)  
    note = Column(Text, nullable=True)       
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Phq9ItemResponse(Base):

    __tablename__ = "phq9_item_responses"

    id = Column(Integer, primary_key=True, index=True)
    intake_id = Column(
        Integer,
        ForeignKey("clinical_intakes.id", ondelete="CASCADE"),
        index=True,
    )
    user_hash = Column(String, index=True, nullable=False)

    question_number = Column(Integer, index=True)    
    prompt = Column(Text, nullable=True)             
    score = Column(Integer, nullable=False)          
    note = Column(Text, nullable=True)               

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    
    is_suicide_item = Column(Boolean, default=False) 



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


# =============================================================================
# PRE-GENERATED AUDIO FOR DAY 2+ USERS (CHANGE #1)
# =============================================================================


class PreGeneratedAudio(Base):
    """
    Stores pre-generated audio for Day 2+ users.
    
    CHANGE #1: Audio is generated after session feedback is submitted,
    so the next session can start instantly without generation delay.
    
    The audio is generated using chills-based personalization from the
    user's last session feedback (emotion_word, chills_detail, session_insight).
    """
    __tablename__ = "pre_generated_audio"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)
    
    # The journey day this audio is FOR (e.g., if user just completed day 2, this is for day 3)
    for_journey_day = Column(Integer, nullable=False, index=True)
    
    # Audio file path (same format as Sessions.audio_path)
    audio_path = Column(String, nullable=False)
    
    # Script text (for reference/debugging)
    script_text = Column(Text, nullable=True)
    
    # Generation parameters used
    track_id = Column(String, nullable=True)
    voice_id = Column(String, nullable=True)
    mood = Column(String, nullable=True)
    schema_hint = Column(String, nullable=True)
    
    # Chills-based context used for generation
    emotion_word = Column(String, nullable=True)
    chills_detail = Column(Text, nullable=True)
    session_insight = Column(Text, nullable=True)
    
    # Status: pending, generating, ready, used, expired, failed
    status = Column(String, default="pending", index=True)
    
    # Error message if generation failed
    error_message = Column(Text, nullable=True)
    
    # When this audio was used (consumed)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Session ID created when this audio was used
    used_session_id = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# =============================================================================
# THERAPIST DASHBOARD MODELS (New)
# =============================================================================


class Therapists(Base):
    """Therapist user accounts - separate from patient Users table"""
    __tablename__ = "therapists"

    id = Column(Integer, primary_key=True, index=True)
    therapist_hash = Column(String, unique=True, index=True, nullable=False)

    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    title = Column(String, nullable=True)  # e.g., "Dr.", "Licensed Therapist"
    
    password_hash = Column(String, nullable=False)  # therapists use email/password only
    
    profile_image_url = Column(String, nullable=True)
    specialty = Column(String, nullable=True)  # e.g., "CBT", "BA", "MI"
    
    # Settings stored as JSON
    settings_json = Column(Text, nullable=True)  # notifications, defaults, etc.
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TherapistPatients(Base):
    """Link table connecting therapists to their patients"""
    __tablename__ = "therapist_patients"

    id = Column(Integer, primary_key=True, index=True)
    therapist_id = Column(
        Integer,
        ForeignKey("therapists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # When this relationship was established
    linked_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Therapist can set initial focus for patient
    initial_focus = Column(String, nullable=True)  # e.g., "Social connection"
    
    # Status of the relationship
    status = Column(String, default="active", index=True)  # active, paused, discharged
    
    # BA week tracking (therapist's view)
    ba_week = Column(Integer, default=1)
    ba_start_date = Column(Date, nullable=True)
    
    # Last session date with therapist (in-person/telehealth)
    last_session_date = Column(Date, nullable=True)
    next_session_date = Column(Date, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TherapistNotes(Base):
    """Session notes written by therapist about a patient"""
    __tablename__ = "therapist_notes"

    id = Column(Integer, primary_key=True, index=True)
    therapist_id = Column(
        Integer,
        ForeignKey("therapists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # Note content
    note_text = Column(Text, nullable=False)
    
    # Optional: link to a specific session date
    session_date = Column(Date, nullable=True)
    
    # Note type: session_note, follow_up, observation, etc.
    note_type = Column(String, default="session_note", index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TherapistAIGuidance(Base):
    """Therapist's guidance for how AI companion should interact with patient"""
    __tablename__ = "therapist_ai_guidance"

    id = Column(Integer, primary_key=True, index=True)
    therapist_id = Column(
        Integer,
        ForeignKey("therapists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # The guidance text that shapes AI responses
    guidance_text = Column(Text, nullable=False)
    
    # Is this guidance currently active?
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TherapistSuggestedActivities(Base):
    """Activities suggested by therapist for a specific patient"""
    __tablename__ = "therapist_suggested_activities"

    id = Column(Integer, primary_key=True, index=True)
    therapist_id = Column(
        Integer,
        ForeignKey("therapists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # Activity details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Categorization
    category = Column(String, nullable=True)  # Connection, Mastery, Physical, etc.
    duration_minutes = Column(Integer, nullable=True)
    barrier_level = Column(String, nullable=True)  # Low, Medium, High
    
    # Source/reason for suggestion
    source_note = Column(String, nullable=True)  # e.g., "From her values", "Grounding"
    
    # Is this suggestion enabled (visible to patient)?
    is_enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PatientInvites(Base):
    """Invitations sent by therapists to patients"""
    __tablename__ = "patient_invites"

    id = Column(Integer, primary_key=True, index=True)
    therapist_id = Column(
        Integer,
        ForeignKey("therapists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # Invite details
    patient_email = Column(String, index=True, nullable=False)
    patient_name = Column(String, nullable=True)
    initial_focus = Column(String, nullable=True)
    
    # Invite token for verification
    invite_token = Column(String, unique=True, index=True, nullable=False)
    
    # Status: pending, accepted, expired, cancelled
    status = Column(String, default="pending", index=True)
    
    # If accepted, link to the patient user
    accepted_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
