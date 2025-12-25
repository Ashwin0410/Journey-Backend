from typing import List, Optional, Dict, Any
from datetime import date, datetime

from pydantic import BaseModel, Field





class IntakeIn(BaseModel):
    
    feeling: Optional[str] = None
    body: Optional[str] = None
    energy: Optional[str] = None
    goal_today: Optional[str] = None
    why_goal: Optional[str] = None
    last_win: Optional[str] = None
    hard_thing: Optional[str] = None
    schema_choice: Optional[str] = None
    postal_code: Optional[str] = None
    place: Optional[str] = None
    user_hash: Optional[str] = None
    journey_day: Optional[int] = None  


class GenerateOut(BaseModel):
    session_id: str
    audio_url: str
    duration_ms: int
    script_excerpt: str
    track_id: str
    voice_id: str
    music_folder: str
    music_file: str
    journey_day: int | None = None
    script_text: str | None = None 




class FeedbackIn(BaseModel):
    session_id: str
    chills: int = Field(ge=0, le=3)
    relevance: int = Field(ge=1, le=5)
    emotion_word: str

    
    chills_option: str | None = None      
    chills_detail: str | None = None      
    session_insight: str | None = None    





class JourneyEventIn(BaseModel):
    session_id: str
    user_hash: str | None = None
    event_type: str  # "chills", "insight", "note", etc.
    t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
    label: str | None = None
    payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# =============================================================================
# ACTIVITY SCHEMAS - BUG FIX (Change 7): Added user_hash for per-user activity scoping
# CHANGE 5: All activities are now place-based with location fields
# =============================================================================

class ActivityBase(BaseModel):
    title: str
    description: str
    life_area: str
    effort_level: str
    reward_type: str | None = None
    default_duration_min: int | None = None
    location_label: str | None = None
    tags: List[str] | None = None
    # BUG FIX (Change 7): Added user_hash to scope activities to individual users
    user_hash: str | None = None
    # CHANGE 5: Google Maps coordinates for directions - ALL activities are place-based
    lat: float | None = None
    lng: float | None = None
    place_id: str | None = None


class ActivityOut(ActivityBase):
    id: int
    # BUG FIX (Change 7): Include user_hash in output for verification
    user_hash: str | None = None

    class Config:
        orm_mode = True


class ActivityRecommendationOut(ActivityOut):
    """
    Extended activity output for recommendations.
    Inherits user_hash from ActivityOut.
    CHANGE 5: All activities now include location data (lat, lng, place_id).
    """
    pass


class ActivityRecommendationListOut(BaseModel):
    
    activities: List[ActivityRecommendationOut]


class ActivityListOut(BaseModel):
    activities: List[ActivityOut]


class ActivityStartIn(BaseModel):
    activity_id: int
    user_hash: str
    session_id: str | None = None 


class ActivitySwapIn(BaseModel):
    activity_id: int 
    user_hash: str


class ActivityCommitIn(BaseModel):
    
    activity_id: int
    user_hash: str


class ActivityCurrentOut(BaseModel):
    activity: Optional[ActivityRecommendationOut] = None





class TodaySummaryOut(BaseModel):
    greeting: str
    current_date: date
    journey_day: Optional[int] = None
    hero_narrative: str
    highlight_terms: List[str]
    has_recent_session: bool
    journey_ready: bool
    journey_cooldown_minutes_remaining: int
    recommended_activity: Optional[ActivityRecommendationOut] = None
    
    postal_code: Optional[str] = None





class UserOut(BaseModel):
    id: int
    user_hash: str
    email: str
    name: Optional[str] = None
    provider: str
    journey_day: Optional[int] = None
    last_journey_date: Optional[date] = None

    
    onboarding_complete: bool
    safety_flag: Optional[int] = None
    last_phq9_date: Optional[date] = None

    class Config:
        orm_mode = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut





class SchemaItemAnswer(BaseModel):
    schema_key: str          
    prompt: Optional[str] = None
    score: int = Field(ge=1, le=6)
    note: Optional[str] = None


class Phq9ItemAnswer(BaseModel):
    question_number: int = Field(ge=1, le=9)
    prompt: Optional[str] = None
    score: int = Field(ge=0, le=3)
    note: Optional[str] = None


class WeeklyPlanIn(BaseModel):
    life_area: str
    life_focus: str
    actions: List[str]
    week_plan_text: str


class IntakeFullIn(BaseModel):
    
    # Pre-intake question: "Has anything been on your mind lately?"
    pre_intake_text: Optional[str] = None
    
    age: Optional[int] = None
    postal_code: Optional[str] = None
    gender: Optional[str] = None

    in_therapy: bool = False
    therapy_type: Optional[str] = None
    therapy_duration: Optional[str] = None

    on_medication: bool = False
    medication_list: Optional[str] = None
    medication_duration: Optional[str] = None

    
    pregnant_or_planning: bool = False
    pregnant_notes: Optional[str] = None
    psychosis_history: bool = False
    psychosis_notes: Optional[str] = None
    privacy_ack: bool = False

    
    schema_items: List[SchemaItemAnswer]

    
    phq9_items: List[Phq9ItemAnswer]

    
    weekly_plan: WeeklyPlanIn
    good_life_answer: str | None = None


class IntakeFullOut(BaseModel):

    id: int
    user_hash: str
    created_at: datetime

    # Pre-intake question: "Has anything been on your mind lately?"
    pre_intake_text: Optional[str] = None

    age: Optional[int] = None
    postal_code: Optional[str] = None
    gender: Optional[str] = None

    in_therapy: bool
    therapy_type: Optional[str] = None
    therapy_duration: Optional[str] = None

    on_medication: bool
    medication_list: Optional[str] = None
    medication_duration: Optional[str] = None

    pregnant_or_planning: bool
    pregnant_notes: Optional[str] = None
    psychosis_history: bool
    psychosis_notes: Optional[str] = None
    privacy_ack: bool

    life_area: Optional[str] = None
    life_focus: Optional[str] = None
    week_actions: List[str]
    week_plan_text: Optional[str] = None
    good_life_answer: Optional[str] = None

    schema_items: List[SchemaItemAnswer]
    phq9_items: List[Phq9ItemAnswer]

    class Config:
        orm_mode = True




class JournalEntryIn(BaseModel):
    user_hash: str
    entry_type: str  # "journal", "insight", "activity", "therapy_future"
    body: str
    title: str | None = None
    session_id: str | None = None
    meta: Dict[str, Any] | None = None
    
    date: Optional[date] = None  # if not provided, defaults to today


class JournalEntryUpdateIn(BaseModel):
    body: Optional[str] = None
    title: Optional[str] = None
    meta: Dict[str, Any] | None = None
    date: Optional[date] = None


class JournalEntryOut(BaseModel):
    id: int
    user_hash: str
    entry_type: str
    body: str
    title: str | None = None
    session_id: str | None = None
    meta: Dict[str, Any] | None = None
    date: date

    class Config:
        orm_mode = True


class JournalTimelineOut(BaseModel):
    future: List[JournalEntryOut]
    today: List[JournalEntryOut]
    past: List[JournalEntryOut]





class TruthProfileIn(BaseModel):
    bio: str


class TruthProfileOut(BaseModel):
    bio: str




class MiniCheckinIn(BaseModel):
    feeling: Optional[str] = None
    body: Optional[str] = None
    energy: Optional[str] = None
    goal_today: Optional[str] = None
    why_goal: Optional[str] = None
    last_win: Optional[str] = None
    hard_thing: Optional[str] = None
    schema_choice: Optional[str] = None
    postal_code: Optional[str] = None
    place: Optional[str] = None


class MiniCheckinOut(MiniCheckinIn):
    id: int
    user_hash: str
    created_at: datetime

    class Config:
        orm_mode = True


class ProfileAnswersOut(BaseModel):
    intake: Optional[IntakeFullOut] = None
    latest_mini_checkin: Optional[MiniCheckinOut] = None




class SchemaItemUpdateByKeyIn(BaseModel):
    schema_key: str
    score: Optional[int] = None
    note: Optional[str] = None


class Phq9ItemUpdateByNumberIn(BaseModel):
    question_number: int = Field(ge=1, le=9)
    score: Optional[int] = None
    note: Optional[str] = None


# ============================================================================
# EMAIL/PASSWORD AUTHENTICATION SCHEMAS
# ============================================================================


class RegisterIn(BaseModel):
    """Schema for user registration with email and password."""
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    """Schema for user login with email and password."""
    email: str
    password: str


# ============================================================================
# PRE-INTAKE SCHEMAS
# ============================================================================


class PreIntakeIn(BaseModel):
    """Schema for pre-intake 'on your mind' submission."""
    pre_intake_text: str


class PreIntakeOut(BaseModel):
    """Schema for pre-intake response."""
    success: bool
    message: str


# ============================================================================
# THERAPIST DASHBOARD SCHEMAS (New)
# ============================================================================


# --- Therapist Auth Schemas ---

class TherapistRegisterIn(BaseModel):
    """Schema for therapist registration."""
    name: str
    email: str
    password: str
    title: Optional[str] = None  # e.g., "Dr.", "Licensed Therapist"
    specialty: Optional[str] = None  # e.g., "CBT", "BA", "MI"


class TherapistLoginIn(BaseModel):
    """Schema for therapist login."""
    email: str
    password: str


class TherapistOut(BaseModel):
    """Schema for therapist data output."""
    id: int
    therapist_hash: str
    email: str
    name: Optional[str] = None
    title: Optional[str] = None
    specialty: Optional[str] = None
    profile_image_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


class TherapistTokenOut(BaseModel):
    """Schema for therapist auth token response."""
    access_token: str
    token_type: str = "bearer"
    therapist: TherapistOut


# --- Therapist Settings Schemas ---

class TherapistSettingsIn(BaseModel):
    """Schema for updating therapist settings."""
    # Notifications
    notify_patient_inactivity: Optional[bool] = None
    notify_milestones: Optional[bool] = None
    notify_daily_summary_email: Optional[bool] = None
    # Defaults
    auto_suggest_activities: Optional[bool] = None
    ai_companion_enabled: Optional[bool] = None


class TherapistSettingsOut(BaseModel):
    """Schema for therapist settings output."""
    notify_patient_inactivity: bool = True
    notify_milestones: bool = True
    notify_daily_summary_email: bool = False
    auto_suggest_activities: bool = True
    ai_companion_enabled: bool = True


# --- Patient Schemas (Therapist View) ---

class PatientSummaryOut(BaseModel):
    """Brief patient info for list views."""
    id: int
    user_hash: str
    email: str
    name: Optional[str] = None
    journey_day: Optional[int] = None
    
    # From TherapistPatients link
    ba_week: Optional[int] = None
    last_session_date: Optional[date] = None
    next_session_date: Optional[date] = None
    status: str = "active"
    initial_focus: Optional[str] = None
    
    # Computed fields
    last_active: Optional[datetime] = None
    activities_this_week: int = 0
    activity_streak: List[bool] = []  # 7 bools for last 7 days

    class Config:
        orm_mode = True


class PatientDetailOut(BaseModel):
    """Full patient detail for therapist view."""
    id: int
    user_hash: str
    email: str
    name: Optional[str] = None
    journey_day: Optional[int] = None
    onboarding_complete: bool = False
    safety_flag: Optional[int] = None
    
    # From TherapistPatients link
    ba_week: Optional[int] = None
    ba_start_date: Optional[date] = None
    last_session_date: Optional[date] = None
    next_session_date: Optional[date] = None
    status: str = "active"
    initial_focus: Optional[str] = None
    linked_at: Optional[datetime] = None
    
    # Clinical data
    intake: Optional[IntakeFullOut] = None
    latest_checkin: Optional[MiniCheckinOut] = None
    
    # Computed/aggregated
    last_active: Optional[datetime] = None
    activities_this_week: int = 0
    activities_last_week: int = 0
    total_sessions: int = 0
    total_journal_entries: int = 0

    class Config:
        orm_mode = True


class PatientListOut(BaseModel):
    """List of patients for therapist dashboard."""
    patients: List[PatientSummaryOut]
    total: int


# --- Invite Schemas ---

class PatientInviteIn(BaseModel):
    """Schema for inviting a new patient."""
    patient_email: str
    patient_name: Optional[str] = None
    initial_focus: Optional[str] = None


class PatientInviteOut(BaseModel):
    """Schema for invite response."""
    id: int
    patient_email: str
    patient_name: Optional[str] = None
    initial_focus: Optional[str] = None
    invite_token: str
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        orm_mode = True


class PatientInviteListOut(BaseModel):
    """List of pending invites."""
    invites: List[PatientInviteOut]


# --- Dashboard Stats Schemas ---

class DashboardStatsOut(BaseModel):
    """Quick stats for therapist dashboard."""
    active_patients: int
    activities_this_week: int
    need_attention: int
    pending_invites: int


class AttentionItemOut(BaseModel):
    """Patient needing attention."""
    patient_id: int
    patient_name: Optional[str] = None
    patient_email: str
    user_hash: str
    
    # Attention reason
    attention_type: str  # "low_activity", "milestone", "high_phq9", "inactive"
    attention_badge: str  # Display text like "Low Activity", "Milestone"
    attention_description: str  # Detailed description
    
    # Context
    last_active: Optional[datetime] = None
    last_session_date: Optional[date] = None
    ba_week: Optional[int] = None
    
    # For milestones
    milestone_type: Optional[str] = None
    milestone_description: Optional[str] = None


class AttentionListOut(BaseModel):
    """List of patients needing attention."""
    urgent: List[AttentionItemOut]
    positive: List[AttentionItemOut]


# --- AI Summary Schemas ---

class PatientAISummaryOut(BaseModel):
    """AI-generated summary for a patient."""
    weekly_summary: str
    whats_working: str
    focus_areas: str
    journal_insight: Optional[str] = None  # Quote from journal
    journal_insight_date: Optional[date] = None
    generated_at: datetime


# --- Activity Heatmap Schemas ---

class ActivityDayOut(BaseModel):
    """Activity level for a single day."""
    date: date
    level: int  # 0-3 (none, low, medium, high)
    activity_count: int
    is_today: bool = False


class ActivityHeatmapOut(BaseModel):
    """Two-week activity heatmap data."""
    days: List[ActivityDayOut]
    total_activities: int
    period_start: date
    period_end: date


# --- Therapist Notes Schemas ---

class TherapistNoteIn(BaseModel):
    """Schema for creating/updating therapist notes."""
    note_text: str
    session_date: Optional[date] = None
    note_type: str = "session_note"  # session_note, follow_up, observation


class TherapistNoteOut(BaseModel):
    """Schema for therapist note output."""
    id: int
    therapist_id: int
    patient_user_id: int
    note_text: str
    session_date: Optional[date] = None
    note_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class TherapistNoteListOut(BaseModel):
    """List of therapist notes."""
    notes: List[TherapistNoteOut]


# --- AI Guidance Schemas ---

class AIGuidanceIn(BaseModel):
    """Schema for creating/updating AI guidance."""
    guidance_text: str
    is_active: bool = True


class AIGuidanceOut(BaseModel):
    """Schema for AI guidance output."""
    id: int
    therapist_id: int
    patient_user_id: int
    guidance_text: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# --- Suggested Activities Schemas ---

class SuggestedActivityIn(BaseModel):
    """Schema for therapist suggesting an activity."""
    title: str
    description: Optional[str] = None
    category: Optional[str] = None  # Connection, Mastery, Physical
    duration_minutes: Optional[int] = None
    barrier_level: Optional[str] = None  # Low, Medium, High
    source_note: Optional[str] = None  # e.g., "From her values"
    is_enabled: bool = True


class SuggestedActivityOut(BaseModel):
    """Schema for suggested activity output."""
    id: int
    therapist_id: int
    patient_user_id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    duration_minutes: Optional[int] = None
    barrier_level: Optional[str] = None
    source_note: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class SuggestedActivityListOut(BaseModel):
    """List of suggested activities."""
    activities: List[SuggestedActivityOut]


class SuggestedActivityToggleIn(BaseModel):
    """Schema for toggling activity enabled state."""
    is_enabled: bool


# --- Resources Schemas ---

class ResourceItemOut(BaseModel):
    """Single resource item."""
    id: str
    title: str
    description: str
    read_time: str  # e.g., "5 min read"
    category: str  # "Foundational", "Assessment", "Clinical", etc.
    section: str  # "ba" (Behavioral Activation), "mi" (Motivational Interviewing), "rewire"


class ResourceSectionOut(BaseModel):
    """Resource section with items."""
    section_id: str
    section_title: str
    items: List[ResourceItemOut]


class ResourceListOut(BaseModel):
    """Full resource library."""
    sections: List[ResourceSectionOut]


# ============================================================================
# ADMIN CONSOLE SCHEMAS (Change 10)
# ============================================================================


# --- Admin Auth Schemas ---

class AdminRegisterIn(BaseModel):
    """Schema for admin registration (typically done by superadmin)."""
    name: str
    email: str
    password: str
    role: str = "admin"  # admin, superadmin, moderator


class AdminLoginIn(BaseModel):
    """Schema for admin login."""
    email: str
    password: str


class AdminOut(BaseModel):
    """Schema for admin data output."""
    id: int
    admin_hash: str
    email: str
    name: Optional[str] = None
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        orm_mode = True


class AdminTokenOut(BaseModel):
    """Schema for admin auth token response."""
    access_token: str
    token_type: str = "bearer"
    admin: AdminOut


# --- Admin User Management Schemas ---

class AdminUserListItemOut(BaseModel):
    """Schema for user item in admin list view."""
    id: int
    user_hash: str
    email: str
    name: Optional[str] = None
    provider: str
    journey_day: Optional[int] = None
    onboarding_complete: bool
    safety_flag: Optional[int] = None
    created_at: datetime
    last_journey_date: Optional[date] = None
    
    # Computed fields
    total_sessions: int = 0
    total_activities: int = 0
    has_therapist: bool = False

    class Config:
        orm_mode = True


class AdminUserListOut(BaseModel):
    """Schema for paginated user list in admin console."""
    users: List[AdminUserListItemOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminTherapistListItemOut(BaseModel):
    """Schema for therapist item in admin list view."""
    id: int
    therapist_hash: str
    email: str
    name: Optional[str] = None
    title: Optional[str] = None
    specialty: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    # Computed fields
    patient_count: int = 0

    class Config:
        orm_mode = True


class AdminTherapistListOut(BaseModel):
    """Schema for paginated therapist list in admin console."""
    therapists: List[AdminTherapistListItemOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# --- Admin Actions Schemas ---

class AdminDeleteUserIn(BaseModel):
    """Schema for deleting a user account."""
    user_id: int
    reason: Optional[str] = None  # Optional reason for audit log
    hard_delete: bool = True  # If true, fully delete (allows re-registration with same email)


class AdminDeleteTherapistIn(BaseModel):
    """Schema for deleting a therapist account."""
    therapist_id: int
    reason: Optional[str] = None  # Optional reason for audit log
    hard_delete: bool = True  # If true, fully delete (allows re-registration with same email)


class AdminActionResultOut(BaseModel):
    """Schema for admin action result."""
    success: bool
    message: str
    action: str
    target_type: str  # "user", "therapist", "admin"
    target_id: int
    target_email: Optional[str] = None


# --- Admin Dashboard Stats Schemas ---

class AdminDashboardStatsOut(BaseModel):
    """Schema for admin dashboard statistics."""
    total_users: int
    total_therapists: int
    total_admins: int
    active_users_today: int
    active_users_week: int
    new_users_today: int
    new_users_week: int
    total_sessions: int
    total_activities_completed: int


# --- Admin Audit Log Schemas ---

class AdminAuditLogOut(BaseModel):
    """Schema for audit log entry output."""
    id: int
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None  # Denormalized for display
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_email: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class AdminAuditLogListOut(BaseModel):
    """Schema for paginated audit log list."""
    logs: List[AdminAuditLogOut]
    total: int
    page: int
    page_size: int
    total_pages: int
