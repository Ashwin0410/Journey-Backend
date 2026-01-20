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


# =============================================================================
# SUGGESTIONS TABLE - Issue #5: General feedback/suggestions from users
# =============================================================================


class Suggestions(Base):
    """
    Stores general user feedback and suggestions.
    
    Issue #5: This is for the 'Share your thoughts' modal where users can
    submit general feedback about activities or the app (separate from
    session-specific Feedback which tracks chills/relevance ratings).
    """
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    
    # The feedback/suggestion text
    feedback = Column(Text, nullable=False)
    
    # Type of feedback: "general", "activity_suggestion", "bug_report", etc.
    type = Column(String, default="general", index=True)
    
    # Optional: link to user who submitted
    user_hash = Column(String, index=True, nullable=True)
    
    # Optional: if feedback is about a specific activity
    activity_id = Column(Integer, index=True, nullable=True)
    
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


# =============================================================================
# ACTIVITIES TABLE - BUG FIX: Added user_hash for per-user activity scoping
# =============================================================================

class Activities(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    
    # BUG FIX (Change 7): Added user_hash to scope activities to individual users
    # Without this, activities generated during intake were shared globally
    # causing Patient B to see Patient A's personalized activities
    user_hash = Column(String, index=True, nullable=True)
    
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
    
    # =============================================================================
    # NEW FIELDS FOR ACTION-BASED ACTIVITY GENERATION
    # =============================================================================
    # The user's action intention text that generated this activity
    # e.g., "Call my mom", "Go for a walk", "Write in journal"
    action_intention = Column(Text, nullable=True)
    
    # Source of the activity: "action_intention", "place_based", "therapist", "system"
    source_type = Column(String, index=True, nullable=True)
    
    # Session ID of the video session that generated this activity
    video_session_id = Column(String, index=True, nullable=True)



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
    
    # =============================================================================
    # NEW FIELD: ML Questionnaire completion tracking
    # =============================================================================
    # True when user has completed the ML personality questionnaire
    # This is separate from onboarding_complete as user may complete onboarding
    # but not have filled out the ML questionnaire yet (legacy users)
    ml_questionnaire_complete = Column(Boolean, default=False, nullable=False)
    
    safety_flag = Column(Integer, nullable=True)        # 0/1/2 style risk level
    last_phq9_date = Column(Date, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # =============================================================================
    # SOFT DELETE SUPPORT (Admin Console Feature)
    # =============================================================================
    # When deleted_at is set, user is considered "deleted":
    # - Cannot sign in (auth routes check deleted_at IS NULL)
    # - Can sign up again with same email (creates new account)
    # - Old data preserved for analytics/audit under old user_hash
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)




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
# PUSH NOTIFICATIONS (CHANGE #7)
# =============================================================================


class PushSubscription(Base):
    """
    Stores Web Push subscription info for sending notifications.
    
    CHANGE #7: Used to notify users when their pre-generated audio is ready,
    activity reminders, and other engagement notifications.
    """
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)
    
    # Push subscription endpoint (unique URL for this device)
    endpoint = Column(Text, nullable=False)
    
    # Encryption keys (from browser's PushSubscription object)
    p256dh_key = Column(String, nullable=False)  # Public key for encryption
    auth_key = Column(String, nullable=False)    # Auth secret
    
    # Device/browser info (for debugging)
    user_agent = Column(String, nullable=True)
    device_type = Column(String, nullable=True)  # mobile, desktop, tablet
    
    # Subscription status
    is_active = Column(Boolean, default=True, index=True)
    
    # Last successful push (for cleanup of stale subscriptions)
    last_push_at = Column(DateTime(timezone=True), nullable=True)
    last_push_status = Column(String, nullable=True)  # success, failed, expired
    
    # Failure tracking (for automatic cleanup)
    consecutive_failures = Column(Integer, default=0)
    
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


# =============================================================================
# ADMIN CONSOLE MODEL (Change 10)
# =============================================================================


class Admins(Base):
    """
    Admin user accounts for managing all accounts in the system.
    
    Change 10: Admins can view and delete both therapist and patient accounts.
    When an account is deleted, the email becomes available for re-registration.
    """
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    admin_hash = Column(String, unique=True, index=True, nullable=False)

    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    
    # Password hash for authentication
    password_hash = Column(String, nullable=False)
    
    # Role: superadmin, admin, moderator (for future role-based access)
    role = Column(String, default="admin", index=True)
    
    # Permissions stored as JSON (for granular control)
    # e.g., {"can_delete_users": true, "can_delete_therapists": true, "can_view_analytics": true}
    permissions_json = Column(Text, nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Last login tracking
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String, nullable=True)
    
    # Audit trail
    created_by_admin_id = Column(Integer, nullable=True)  # Which admin created this admin
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AdminAuditLog(Base):
    """
    Audit log for admin actions.
    
    Change 10: Tracks all admin actions for accountability and security.
    """
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(
        Integer,
        ForeignKey("admins.id", ondelete="SET NULL"),
        index=True,
        nullable=True,  # Allow null if admin is deleted
    )
    
    # Action details
    action = Column(String, nullable=False, index=True)  # e.g., "delete_user", "delete_therapist", "view_users"
    target_type = Column(String, nullable=True, index=True)  # "user", "therapist", "admin"
    target_id = Column(Integer, nullable=True)  # ID of the affected record
    target_email = Column(String, nullable=True)  # Email for reference after deletion
    
    # Additional context stored as JSON
    # e.g., {"reason": "User requested deletion", "user_name": "John Doe"}
    details_json = Column(Text, nullable=True)
    
    # Request metadata
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# STIMULI SUGGESTION MODEL (Required by journey.py video endpoints)
# =============================================================================


class StimuliSuggestion(Base):
    """
    Stores ML-predicted video suggestions for users.
    
    Created when user completes the ML questionnaire (/api/intake/ml-questionnaire).
    Used by /api/journey/video-suggestion to serve ranked video recommendations.
    
    Day 1 = rank 1 video, Day 2 = rank 2 video, etc.
    """
    __tablename__ = "stimuli_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)
    
    # Video identification
    stimulus_rank = Column(Integer, index=True, nullable=False)  # 1, 2, 3... (maps to journey day)
    stimulus_name = Column(String, nullable=False)
    stimulus_url = Column(String, nullable=False)  # YouTube URL
    stimulus_description = Column(Text, nullable=True)
    
    # ML prediction score (higher = better match for user)
    score = Column(Float, nullable=True)
    
    # Link to questionnaire that generated this suggestion
    questionnaire_id = Column(Integer, nullable=True)
    
    # Tracking
    was_shown = Column(Boolean, default=False)
    was_watched = Column(Boolean, default=False)
    was_completed = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# ML VIDEO REFACTOR MODELS
# =============================================================================


class MLQuestionnaire(Base):
    """
    ML Video Refactor: Stores user responses to the ML questionnaire.
    
    The questionnaire collects data for the ML personalization system including:
    - DPES (Dispositional Positive Emotion Scale) items
    - NEO-FFI (Openness to Experience) items  
    - KAMF (Absorption/Music-induced chills) items
    
    Responses are stored as JSON for flexibility as questions may evolve.
    """
    __tablename__ = "ml_questionnaires"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)
    
    # All answers stored as JSON: [{"question_code": "DPES_1", "value": 5}, ...]
    answers_json = Column(Text, nullable=False)
    
    # Computed scores (cached for quick access)
    dpes_awe_score = Column(Float, nullable=True)  # Awe subscale
    dpes_joy_score = Column(Float, nullable=True)  # Joy subscale
    neo_openness_score = Column(Float, nullable=True)  # Openness to Experience
    kamf_absorption_score = Column(Float, nullable=True)  # Absorption in music
    
    # Completion status
    complete = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class VideoStimulus(Base):
    """
    ML Video Refactor: Catalog of available video stimuli.
    
    Stores metadata about videos that can be suggested to users.
    Videos are matched to users based on their ML questionnaire responses.
    """
    __tablename__ = "video_stimuli"

    id = Column(Integer, primary_key=True, index=True)
    
    # Video identification
    stimulus_name = Column(String, nullable=False)
    stimulus_description = Column(Text, nullable=True)
    
    # Video URLs
    stimulus_url = Column(String, nullable=False)  # YouTube URL or embed URL
    embed_url = Column(String, nullable=True)  # Direct embed URL if different
    thumbnail_url = Column(String, nullable=True)
    
    # Video metadata
    duration_seconds = Column(Integer, nullable=True)
    category = Column(String, index=True, nullable=True)  # nature, music, speech, etc.
    tags_json = Column(Text, nullable=True)  # ["uplifting", "orchestral", "cinematic"]
    
    # ML matching features (for personalization algorithm)
    # These scores help match videos to user profiles
    awe_potential = Column(Float, nullable=True)  # 0-1 score for awe-inducing potential
    emotional_valence = Column(Float, nullable=True)  # -1 to 1 (negative to positive)
    arousal_level = Column(Float, nullable=True)  # 0-1 (calm to exciting)
    
    # Usage stats
    times_shown = Column(Integer, default=0)
    times_completed = Column(Integer, default=0)
    avg_chills_count = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class VideoSession(Base):
    """
    ML Video Refactor: Tracks individual video watching sessions.
    
    Created when a user starts watching a video, updated as they interact.
    Links to chills timestamps, body map data, and post-video responses.
    """
    __tablename__ = "video_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)  # Client-generated UUID
    user_hash = Column(String, index=True, nullable=False)
    video_id = Column(Integer, ForeignKey("video_stimuli.id"), index=True, nullable=False)
    
    # Session timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Viewing data
    watched_duration_seconds = Column(Float, nullable=True)
    completed = Column(Boolean, default=False)
    
    # Aggregated chills data (updated after session)
    chills_count = Column(Integer, default=0)
    body_map_spots = Column(Integer, default=0)
    
    # Post-video response submitted
    has_response = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChillsTimestamp(Base):
    """
    ML Video Refactor: Records individual chills moments during video playback.
    
    Each time a user presses the chills button, a timestamp is recorded.
    Multiple timestamps can exist per session.
    """
    __tablename__ = "chills_timestamps"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("video_sessions.session_id"), index=True, nullable=False)
    user_hash = Column(String, index=True, nullable=True)
    
    # Time in the video when chills occurred (seconds)
    video_time_seconds = Column(Float, nullable=False)
    
    # =============================================================================
    # NEW FIELD: Video name for tracking which video was being watched
    # =============================================================================
    video_name = Column(String, nullable=True)
    
    # Optional: intensity if we add a slider later
    intensity = Column(Integer, nullable=True)  # 1-5 scale
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChillsBodyMap(Base):
    """
    ML Video Refactor: Stores body map data from post-video check-in.
    
    Users can mark where they felt sensations on a body diagram.
    Spots are stored as JSON array of {x_percent, y_percent} coordinates.
    """
    __tablename__ = "chills_body_maps"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("video_sessions.session_id"), index=True, nullable=False)
    user_hash = Column(String, index=True, nullable=True)
    
    # Body map spots as JSON: [{"x_percent": 50.0, "y_percent": 30.0}, ...]
    spots_json = Column(Text, nullable=False)
    spot_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChillsResponse(Base):
    """
    ML Video Refactor: Stores post-video response data.
    
    After watching a video and optionally marking body sensations,
    users complete a 3-step form: Insights -> Value -> Action.
    """
    __tablename__ = "chills_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("video_sessions.session_id"), unique=True, index=True, nullable=False)
    user_hash = Column(String, index=True, nullable=True)
    
    # Step 1: Insights
    insights_text = Column(Text, nullable=True)  # "What stood out to you?"
    
    # Step 2: Value selection
    value_selected = Column(String, nullable=True)  # Connection, Growth, Peace, etc.
    value_custom = Column(String, nullable=True)  # If "Other" was selected
    
    # Step 3: Action commitment
    action_selected = Column(String, nullable=True)  # Predefined action
    action_custom = Column(String, nullable=True)  # If "Other" was selected
    
    # Computed field for convenience
    action_today = Column(String, nullable=True)  # Final action (selected or custom)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VideoSuggestionLog(Base):
    """
    ML Video Refactor: Logs video suggestions for analysis and debugging.
    
    Tracks which videos were suggested to users and why,
    enabling analysis of the recommendation algorithm.
    """
    __tablename__ = "video_suggestion_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)
    video_id = Column(Integer, ForeignKey("video_stimuli.id"), index=True, nullable=False)
    
    # Why this video was suggested
    suggestion_reason = Column(String, nullable=True)  # "high_awe_match", "new_user_default", etc.
    match_score = Column(Float, nullable=True)  # 0-1 score from ML algorithm
    
    # User response
    was_watched = Column(Boolean, default=False)
    was_completed = Column(Boolean, default=False)
    chills_count = Column(Integer, nullable=True)
    
    # Context
    journey_day = Column(Integer, nullable=True)
    questionnaire_id = Column(Integer, ForeignKey("ml_questionnaires.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# MISSING MODELS REQUIRED BY ROUTES
# =============================================================================


class MLQuestionnaireResponse(Base):
    """
    ML Questionnaire with individual columns for each question.
    Required by: routes/intake.py
    """
    __tablename__ = "ml_questionnaire_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_hash = Column(String, index=True, nullable=False)
    
    # DPES questions (1-7 scale)
    dpes_1 = Column(Integer, nullable=True)
    dpes_4 = Column(Integer, nullable=True)
    dpes_29 = Column(Integer, nullable=True)
    
    # NEO-FFI questions (1-5 scale)
    neo_ffi_10 = Column(Integer, nullable=True)
    neo_ffi_14 = Column(Integer, nullable=True)
    neo_ffi_16 = Column(Integer, nullable=True)
    neo_ffi_45 = Column(Integer, nullable=True)
    neo_ffi_46 = Column(Integer, nullable=True)
    
    # KAMF question (1-7 scale)
    kamf_4_1 = Column(Integer, nullable=True)
    
    # Demographics
    age = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    ethnicity = Column(String, nullable=True)
    education = Column(String, nullable=True)
    depression_status = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BodyMapSpot(Base):
    """
    Individual body map spot with x,y coordinates.
    Required by: routes/chills.py
    """
    __tablename__ = "body_map_spots"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    x_percent = Column(Float, nullable=False)
    y_percent = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PostVideoResponse(Base):
    """
    Post-video response (insights, value, action).
    Required by: routes/chills.py, routes/activity.py
    """
    __tablename__ = "post_video_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    user_hash = Column(String, index=True, nullable=True)
    insights_text = Column(Text, nullable=True)
    value_selected = Column(String, nullable=True)
    value_custom = Column(String, nullable=True)
    action_selected = Column(String, nullable=True)
    action_custom = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
