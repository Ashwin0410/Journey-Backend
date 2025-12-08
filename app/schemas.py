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

    # Post-session questionnaire fields
    chills_option: str | None = None      # "yes", "subtle", "no"
    chills_detail: str | None = None      # What sparked that moment?
    session_insight: str | None = None    # Any insights from this session?
    
    # ISSUE 4 & 5: Array of timestamps (in seconds) when user pressed chills button
    chills_moments: List[float] | None = None





class JourneyEventIn(BaseModel):
    session_id: str
    user_hash: str | None = None
    event_type: str  # "chills", "insight", "note", etc.
    t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
    label: str | None = None
    payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)




class ActivityBase(BaseModel):
    title: str
    description: str
    life_area: str
    effort_level: str
    reward_type: str | None = None
    default_duration_min: int | None = None
    location_label: str | None = None
    tags: List[str] | None = None


class ActivityOut(ActivityBase):
    id: int

    class Config:
        orm_mode = True


class ActivityRecommendationOut(ActivityOut):
   
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
    good_life_answer: str


class IntakeFullOut(BaseModel):

    id: int
    user_hash: str
    created_at: datetime

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
