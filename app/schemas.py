
# from typing import List, Optional, Dict, Any
# from datetime import date
# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     feeling: str
#     body: str
#     energy: str
#     goal_today: str
#     why_goal: str
#     last_win: str
#     hard_thing: str
#     schema_choice: str
#     postal_code: str
#     place: str | None = None
#     user_hash: str | None = None
#     journey_day: int | None = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]










# from typing import List, Optional, Dict, Any
# from datetime import date, datetime

# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     feeling: str
#     body: str
#     energy: str
#     goal_today: str
#     why_goal: str
#     last_win: str
#     hard_thing: str
#     schema_choice: str
#     postal_code: str
#     place: str | None = None
#     user_hash: str | None = None
#     journey_day: int | None = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str

#     # NEW: richer post-session form (optional)
#     chills_option: str | None = None       # "yes" | "subtle" | "no"
#     chills_detail: str | None = None       # "What sparked that moment?"
#     session_insight: str | None = None     # "Any insights from this session?"


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     # NEW: onboarding + safety flags exposed to frontend
#     onboarding_complete: bool
#     safety_flag: Optional[int] = None
#     last_phq9_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Full Intake / Assessments ---------


# class SchemaItemAnswer(BaseModel):
#     schema_key: str          # e.g. "defectiveness_shame"
#     prompt: Optional[str] = None
#     score: int = Field(ge=1, le=6)
#     note: Optional[str] = None


# class Phq9ItemAnswer(BaseModel):
#     question_number: int = Field(ge=1, le=9)
#     prompt: Optional[str] = None
#     score: int = Field(ge=0, le=3)
#     note: Optional[str] = None


# class WeeklyPlanIn(BaseModel):
#     life_area: str
#     life_focus: str
#     actions: List[str]
#     week_plan_text: str


# class IntakeFullIn(BaseModel):
#     """
#     Payload for the entire intake wizard after first Google login.
#     Matches Felix's flow:
#       1) Basic info
#       2) Schema personalization
#       3) Safety screening
#       4) PHQ-9
#       5) Weekly plan + 90-year reflection
#     """
#     # Basic info
#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool = False
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool = False
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     # Safety
#     pregnant_or_planning: bool = False
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool = False
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool = False

#     # Schema items
#     schema_items: List[SchemaItemAnswer]

#     # PHQ-9
#     phq9_items: List[Phq9ItemAnswer]

#     # Weekly plan + 90-year reflection
#     weekly_plan: WeeklyPlanIn
#     good_life_answer: str


# class IntakeFullOut(BaseModel):
#     """
#     Read-back model in case we want to show intake summary later.
#     """
#     id: int
#     user_hash: str
#     created_at: datetime

#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     pregnant_or_planning: bool
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool

#     life_area: Optional[str] = None
#     life_focus: Optional[str] = None
#     week_actions: List[str]
#     week_plan_text: Optional[str] = None
#     good_life_answer: Optional[str] = None

#     schema_items: List[SchemaItemAnswer]
#     phq9_items: List[Phq9ItemAnswer]

#     class Config:
#         orm_mode = True


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]






# from typing import List, Optional, Dict, Any
# from datetime import date, datetime

# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     feeling: str
#     body: str
#     energy: str
#     goal_today: str
#     why_goal: str
#     last_win: str
#     hard_thing: str
#     schema_choice: str
#     postal_code: str
#     place: str | None = None
#     user_hash: str | None = None
#     journey_day: int | None = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str

#     # NEW: richer post-session form (optional)
#     chills_option: str | None = None       # "yes" | "subtle" | "no"
#     chills_detail: str | None = None       # "What sparked that moment?"
#     session_insight: str | None = None     # "Any insights from this session?"


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     # NEW: onboarding + safety flags exposed to frontend
#     onboarding_complete: bool
#     safety_flag: Optional[int] = None
#     last_phq9_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Full Intake / Assessments ---------


# class SchemaItemAnswer(BaseModel):
#     schema_key: str          # e.g. "defectiveness_shame"
#     prompt: Optional[str] = None
#     score: int = Field(ge=1, le=6)
#     note: Optional[str] = None


# class Phq9ItemAnswer(BaseModel):
#     question_number: int = Field(ge=1, le=9)
#     prompt: Optional[str] = None
#     score: int = Field(ge=0, le=3)
#     note: Optional[str] = None


# class WeeklyPlanIn(BaseModel):
#     life_area: str
#     life_focus: str
#     actions: List[str]
#     week_plan_text: str


# class IntakeFullIn(BaseModel):
#     """
#     Payload for the entire intake wizard after first Google login.
#     Matches Felix's flow:
#       1) Basic info
#       2) Schema personalization
#       3) Safety screening
#       4) PHQ-9
#       5) Weekly plan + 90-year reflection
#     """
#     # Basic info
#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool = False
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool = False
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     # Safety
#     pregnant_or_planning: bool = False
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool = False
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool = False

#     # Schema items
#     schema_items: List[SchemaItemAnswer]

#     # PHQ-9
#     phq9_items: List[Phq9ItemAnswer]

#     # Weekly plan + 90-year reflection
#     weekly_plan: WeeklyPlanIn
#     good_life_answer: str


# class IntakeFullOut(BaseModel):
#     """
#     Read-back model in case we want to show intake summary later.
#     """
#     id: int
#     user_hash: str
#     created_at: datetime

#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     pregnant_or_planning: bool
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool

#     life_area: Optional[str] = None
#     life_focus: Optional[str] = None
#     week_actions: List[str]
#     week_plan_text: Optional[str] = None
#     good_life_answer: Optional[str] = None

#     schema_items: List[SchemaItemAnswer]
#     phq9_items: List[Phq9ItemAnswer]

#     class Config:
#         orm_mode = True


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]




# from typing import List, Optional, Dict, Any
# from datetime import date, datetime

# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     feeling: str
#     body: str
#     energy: str
#     goal_today: str
#     why_goal: str
#     last_win: str
#     hard_thing: str
#     schema_choice: str
#     postal_code: str
#     place: str | None = None
#     user_hash: str | None = None
#     journey_day: int | None = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str

#     # NEW: richer post-session form (optional)
#     chills_option: str | None = None       # "yes" | "subtle" | "no"
#     chills_detail: str | None = None       # "What sparked that moment?"
#     session_insight: str | None = None     # "Any insights from this session?"


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# # --------- Home / Today view ---------


# class TodaySummaryOut(BaseModel):
#     greeting: str
#     current_date: date
#     journey_day: Optional[int] = None
#     hero_narrative: str
#     highlight_terms: List[str]
#     has_recent_session: bool
#     journey_ready: bool
#     journey_cooldown_minutes_remaining: int
#     recommended_activity: Optional[ActivityRecommendationOut] = None


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     # NEW: onboarding + safety flags exposed to frontend
#     onboarding_complete: bool
#     safety_flag: Optional[int] = None
#     last_phq9_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Full Intake / Assessments ---------


# class SchemaItemAnswer(BaseModel):
#     schema_key: str          # e.g. "defectiveness_shame"
#     prompt: Optional[str] = None
#     score: int = Field(ge=1, le=6)
#     note: Optional[str] = None


# class Phq9ItemAnswer(BaseModel):
#     question_number: int = Field(ge=1, le=9)
#     prompt: Optional[str] = None
#     score: int = Field(ge=0, le=3)
#     note: Optional[str] = None


# class WeeklyPlanIn(BaseModel):
#     life_area: str
#     life_focus: str
#     actions: List[str]
#     week_plan_text: str


# class IntakeFullIn(BaseModel):
#     """
#     Payload for the entire intake wizard after first Google login.
#     Matches Felix's flow:
#       1) Basic info
#       2) Schema personalization
#       3) Safety screening
#       4) PHQ-9
#       5) Weekly plan + 90-year reflection
#     """
#     # Basic info
#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool = False
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool = False
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     # Safety
#     pregnant_or_planning: bool = False
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool = False
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool = False

#     # Schema items
#     schema_items: List[SchemaItemAnswer]

#     # PHQ-9
#     phq9_items: List[Phq9ItemAnswer]

#     # Weekly plan + 90-year reflection
#     weekly_plan: WeeklyPlanIn
#     good_life_answer: str


# class IntakeFullOut(BaseModel):
#     """
#     Read-back model in case we want to show intake summary later.
#     """
#     id: int
#     user_hash: str
#     created_at: datetime

#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     pregnant_or_planning: bool
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool

#     life_area: Optional[str] = None
#     life_focus: Optional[str] = None
#     week_actions: List[str]
#     week_plan_text: Optional[str] = None
#     good_life_answer: Optional[str] = None

#     schema_items: List[SchemaItemAnswer]
#     phq9_items: List[Phq9ItemAnswer]

#     class Config:
#         orm_mode = True


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryUpdateIn(BaseModel):
#     """
#     Partial update model for editing a journal / insight / activity entry.
#     All fields are optional; only provided ones are changed.
#     """
#     body: Optional[str] = None
#     title: Optional[str] = None
#     meta: Dict[str, Any] | None = None
#     date: Optional[date] = None


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]


# # --------- Settings / Truth Profile ---------


# class TruthProfileIn(BaseModel):
#     bio: str


# class TruthProfileOut(BaseModel):
#     bio: str




# from typing import List, Optional, Dict, Any
# from datetime import date, datetime

# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     feeling: str
#     body: str
#     energy: str
#     goal_today: str
#     why_goal: str
#     last_win: str
#     hard_thing: str
#     schema_choice: str
#     postal_code: str
#     place: str | None = None
#     user_hash: str | None = None
#     journey_day: int | None = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str

#     # NEW: richer post-session form (optional)
#     chills_option: str | None = None       # "yes" | "subtle" | "no"
#     chills_detail: str | None = None       # "What sparked that moment?"
#     session_insight: str | None = None     # "Any insights from this session?"


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# # --------- Home / Today view ---------


# class TodaySummaryOut(BaseModel):
#     greeting: str
#     current_date: date
#     journey_day: Optional[int] = None
#     hero_narrative: str
#     highlight_terms: List[str]
#     has_recent_session: bool
#     journey_ready: bool
#     journey_cooldown_minutes_remaining: int
#     recommended_activity: Optional[ActivityRecommendationOut] = None
#     postal_code: Optional[str] = None  # NEW: exposed to frontend for maps/activity


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     # NEW: onboarding + safety flags exposed to frontend
#     onboarding_complete: bool
#     safety_flag: Optional[int] = None
#     last_phq9_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Full Intake / Assessments ---------


# class SchemaItemAnswer(BaseModel):
#     schema_key: str          # e.g. "defectiveness_shame"
#     prompt: Optional[str] = None
#     score: int = Field(ge=1, le=6)
#     note: Optional[str] = None


# class Phq9ItemAnswer(BaseModel):
#     question_number: int = Field(ge=1, le=9)
#     prompt: Optional[str] = None
#     score: int = Field(ge=0, le=3)
#     note: Optional[str] = None


# class WeeklyPlanIn(BaseModel):
#     life_area: str
#     life_focus: str
#     actions: List[str]
#     week_plan_text: str


# class IntakeFullIn(BaseModel):
#     """
#     Payload for the entire intake wizard after first Google login.
#     Matches Felix's flow:
#       1) Basic info
#       2) Schema personalization
#       3) Safety screening
#       4) PHQ-9
#       5) Weekly plan + 90-year reflection
#     """
#     # Basic info
#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool = False
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool = False
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     # Safety
#     pregnant_or_planning: bool = False
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool = False
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool = False

#     # Schema items
#     schema_items: List[SchemaItemAnswer]

#     # PHQ-9
#     phq9_items: List[Phq9ItemAnswer]

#     # Weekly plan + 90-year reflection
#     weekly_plan: WeeklyPlanIn
#     good_life_answer: str


# class IntakeFullOut(BaseModel):
#     """
#     Read-back model in case we want to show intake summary later.
#     """
#     id: int
#     user_hash: str
#     created_at: datetime

#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     pregnant_or_planning: bool
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool

#     life_area: Optional[str] = None
#     life_focus: Optional[str] = None
#     week_actions: List[str]
#     week_plan_text: Optional[str] = None
#     good_life_answer: Optional[str] = None

#     schema_items: List[SchemaItemAnswer]
#     phq9_items: List[Phq9ItemAnswer]

#     class Config:
#         orm_mode = True


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryUpdateIn(BaseModel):
#     """
#     Partial update model for editing a journal / insight / activity entry.
#     All fields are optional; only provided ones are changed.
#     """
#     body: Optional[str] = None
#     title: Optional[str] = None
#     meta: Dict[str, Any] | None = None
#     date: Optional[date] = None


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]


# # --------- Settings / Truth Profile ---------


# class TruthProfileIn(BaseModel):
#     bio: str


# class TruthProfileOut(BaseModel):
#     bio: str









# from typing import List, Optional, Dict, Any
# from datetime import date, datetime

# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     feeling: str
#     body: str
#     energy: str
#     goal_today: str
#     why_goal: str
#     last_win: str
#     hard_thing: str
#     schema_choice: str
#     postal_code: str
#     place: str | None = None
#     user_hash: str | None = None
#     journey_day: int | None = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str

#     # NEW: richer post-session form (optional)
#     chills_option: str | None = None       # "yes" | "subtle" | "no"
#     chills_detail: str | None = None       # "What sparked that moment?"
#     session_insight: str | None = None     # "Any insights from this session?"


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# # --------- Home / Today view ---------


# class TodaySummaryOut(BaseModel):
#     greeting: str
#     current_date: date
#     journey_day: Optional[int] = None
#     hero_narrative: str
#     highlight_terms: List[str]
#     has_recent_session: bool
#     journey_ready: bool
#     journey_cooldown_minutes_remaining: int
#     recommended_activity: Optional[ActivityRecommendationOut] = None
#     # 👇 Expose postal_code so the frontend can pass it into recommendation/generation
#     postal_code: Optional[str] = None


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     # NEW: onboarding + safety flags exposed to frontend
#     onboarding_complete: bool
#     safety_flag: Optional[int] = None
#     last_phq9_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Full Intake / Assessments ---------


# class SchemaItemAnswer(BaseModel):
#     schema_key: str          # e.g. "defectiveness_shame"
#     prompt: Optional[str] = None
#     score: int = Field(ge=1, le=6)
#     note: Optional[str] = None


# class Phq9ItemAnswer(BaseModel):
#     question_number: int = Field(ge=1, le=9)
#     prompt: Optional[str] = None
#     score: int = Field(ge=0, le=3)
#     note: Optional[str] = None


# class WeeklyPlanIn(BaseModel):
#     life_area: str
#     life_focus: str
#     actions: List[str]
#     week_plan_text: str


# class IntakeFullIn(BaseModel):
#     """
#     Payload for the entire intake wizard after first Google login.
#     Matches Felix's flow:
#       1) Basic info
#       2) Schema personalization
#       3) Safety screening
#       4) PHQ-9
#       5) Weekly plan + 90-year reflection
#     """
#     # Basic info
#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool = False
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool = False
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     # Safety
#     pregnant_or_planning: bool = False
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool = False
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool = False

#     # Schema items
#     schema_items: List[SchemaItemAnswer]

#     # PHQ-9
#     phq9_items: List[Phq9ItemAnswer]

#     # Weekly plan + 90-year reflection
#     weekly_plan: WeeklyPlanIn
#     good_life_answer: str


# class IntakeFullOut(BaseModel):
#     """
#     Read-back model in case we want to show intake summary later.
#     """
#     id: int
#     user_hash: str
#     created_at: datetime

#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     pregnant_or_planning: bool
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool

#     life_area: Optional[str] = None
#     life_focus: Optional[str] = None
#     week_actions: List[str]
#     week_plan_text: Optional[str] = None
#     good_life_answer: Optional[str] = None

#     schema_items: List[SchemaItemAnswer]
#     phq9_items: List[Phq9ItemAnswer]

#     class Config:
#         orm_mode = True


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryUpdateIn(BaseModel):
#     """
#     Partial update model for editing a journal / insight / activity entry.
#     All fields are optional; only provided ones are changed.
#     """
#     body: Optional[str] = None
#     title: Optional[str] = None
#     meta: Dict[str, Any] | None = None
#     date: Optional[date] = None


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]


# # --------- Settings / Truth Profile ---------


# class TruthProfileIn(BaseModel):
#     bio: str


# class TruthProfileOut(BaseModel):
#     bio: str








# from typing import List, Optional, Dict, Any
# from datetime import date, datetime

# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     feeling: str
#     body: str
#     energy: str
#     goal_today: str
#     why_goal: str
#     last_win: str
#     hard_thing: str
#     schema_choice: str
#     postal_code: str
#     place: str | None = None
#     user_hash: str | None = None
#     journey_day: int | None = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str

#     # NEW: richer post-session form (optional)
#     chills_option: str | None = None       # "yes" | "subtle" | "no"
#     chills_detail: str | None = None       # "What sparked that moment?"
#     session_insight: str | None = None     # "Any insights from this session?"


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# class ActivityCommitIn(BaseModel):
#     """Commit (persist) a specific activity as today's pick."""
#     activity_id: int
#     user_hash: str


# class ActivityCurrentOut(BaseModel):
#     activity: Optional[ActivityRecommendationOut] = None


# # --------- Home / Today view ---------


# class TodaySummaryOut(BaseModel):
#     greeting: str
#     current_date: date
#     journey_day: Optional[int] = None
#     hero_narrative: str
#     highlight_terms: List[str]
#     has_recent_session: bool
#     journey_ready: bool
#     journey_cooldown_minutes_remaining: int
#     recommended_activity: Optional[ActivityRecommendationOut] = None
#     # 👇 Expose postal_code so the frontend can pass it into recommendation/generation
#     postal_code: Optional[str] = None


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     # NEW: onboarding + safety flags exposed to frontend
#     onboarding_complete: bool
#     safety_flag: Optional[int] = None
#     last_phq9_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Full Intake / Assessments ---------


# class SchemaItemAnswer(BaseModel):
#     schema_key: str          # e.g. "defectiveness_shame"
#     prompt: Optional[str] = None
#     score: int = Field(ge=1, le=6)
#     note: Optional[str] = None


# class Phq9ItemAnswer(BaseModel):
#     question_number: int = Field(ge=1, le=9)
#     prompt: Optional[str] = None
#     score: int = Field(ge=0, le=3)
#     note: Optional[str] = None


# class WeeklyPlanIn(BaseModel):
#     life_area: str
#     life_focus: str
#     actions: List[str]
#     week_plan_text: str


# class IntakeFullIn(BaseModel):
#     """
#     Payload for the entire intake wizard after first Google login.
#     Matches Felix's flow:
#       1) Basic info
#       2) Schema personalization
#       3) Safety screening
#       4) PHQ-9
#       5) Weekly plan + 90-year reflection
#     """
#     # Basic info
#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool = False
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool = False
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     # Safety
#     pregnant_or_planning: bool = False
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool = False
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool = False

#     # Schema items
#     schema_items: List[SchemaItemAnswer]

#     # PHQ-9
#     phq9_items: List[Phq9ItemAnswer]

#     # Weekly plan + 90-year reflection
#     weekly_plan: WeeklyPlanIn
#     good_life_answer: str


# class IntakeFullOut(BaseModel):
#     """
#     Read-back model in case we want to show intake summary later.
#     """
#     id: int
#     user_hash: str
#     created_at: datetime

#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     pregnant_or_planning: bool
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool

#     life_area: Optional[str] = None
#     life_focus: Optional[str] = None
#     week_actions: List[str]
#     week_plan_text: Optional[str] = None
#     good_life_answer: Optional[str] = None

#     schema_items: List[SchemaItemAnswer]
#     phq9_items: List[Phq9ItemAnswer]

#     class Config:
#         orm_mode = True


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryUpdateIn(BaseModel):
#     """
#     Partial update model for editing a journal / insight / activity entry.
#     All fields are optional; only provided ones are changed.
#     """
#     body: Optional[str] = None
#     title: Optional[str] = None
#     meta: Dict[str, Any] | None = None
#     date: Optional[date] = None


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]


# # --------- Settings / Truth Profile ---------


# class TruthProfileIn(BaseModel):
#     bio: str


# class TruthProfileOut(BaseModel):
#     bio: str


# from typing import List, Optional, Dict, Any
# from datetime import date, datetime

# from pydantic import BaseModel, Field


# # --------- Intake & Journey generation ---------


# class IntakeIn(BaseModel):
#     """
#     Day-1 intake OR Day-2+ mini check-in.

#     All fields are optional so the frontend can submit a sparse payload.
#     The /api/journey/generate route will enrich with fallbacks (history/Day-1)
#     and apply sensible defaults.
#     """
#     feeling: Optional[str] = None
#     body: Optional[str] = None
#     energy: Optional[str] = None
#     goal_today: Optional[str] = None
#     why_goal: Optional[str] = None
#     last_win: Optional[str] = None
#     hard_thing: Optional[str] = None
#     schema_choice: Optional[str] = None
#     postal_code: Optional[str] = None
#     place: Optional[str] = None
#     user_hash: Optional[str] = None
#     journey_day: Optional[int] = None  # streak-style day selector


# class GenerateOut(BaseModel):
#     session_id: str
#     audio_url: str
#     duration_ms: int
#     script_excerpt: str
#     track_id: str
#     voice_id: str
#     music_folder: str
#     music_file: str
#     journey_day: int | None = None
#     script_text: str | None = None  # full script returned in response


# # --------- Post-session feedback ---------


# class FeedbackIn(BaseModel):
#     session_id: str
#     chills: int = Field(ge=0, le=3)
#     relevance: int = Field(ge=1, le=5)
#     emotion_word: str

#     # NEW: richer post-session form (optional)
#     chills_option: str | None = None       # "yes" | "subtle" | "no"
#     chills_detail: str | None = None       # "What sparked that moment?"
#     session_insight: str | None = None     # "Any insights from this session?"


# # --------- Per-moment Journey events (chills button, insights, etc.) ---------


# class JourneyEventIn(BaseModel):
#     session_id: str
#     user_hash: str | None = None
#     event_type: str  # "chills", "insight", "note", etc.
#     t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
#     label: str | None = None
#     payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# # --------- Activity engine (recommendation + tracking) ---------


# class ActivityBase(BaseModel):
#     title: str
#     description: str
#     life_area: str
#     effort_level: str
#     reward_type: str | None = None
#     default_duration_min: int | None = None
#     location_label: str | None = None
#     tags: List[str] | None = None


# class ActivityOut(ActivityBase):
#     id: int

#     class Config:
#         orm_mode = True


# class ActivityRecommendationOut(ActivityOut):
#     """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
#     pass


# class ActivityRecommendationListOut(BaseModel):
#     """Used when we want to return multiple recommendations at once."""
#     activities: List[ActivityRecommendationOut]


# class ActivityListOut(BaseModel):
#     activities: List[ActivityOut]


# class ActivityStartIn(BaseModel):
#     activity_id: int
#     user_hash: str
#     session_id: str | None = None  # link to Journey session if triggered from a session


# class ActivitySwapIn(BaseModel):
#     activity_id: int  # the one they swapped away from
#     user_hash: str


# class ActivityCommitIn(BaseModel):
#     """Commit (persist) a specific activity as today's pick."""
#     activity_id: int
#     user_hash: str


# class ActivityCurrentOut(BaseModel):
#     activity: Optional[ActivityRecommendationOut] = None


# # --------- Home / Today view ---------


# class TodaySummaryOut(BaseModel):
#     greeting: str
#     current_date: date
#     journey_day: Optional[int] = None
#     hero_narrative: str
#     highlight_terms: List[str]
#     has_recent_session: bool
#     journey_ready: bool
#     journey_cooldown_minutes_remaining: int
#     recommended_activity: Optional[ActivityRecommendationOut] = None
#     # 👇 Expose postal_code so the frontend can pass it into recommendation/generation
#     postal_code: Optional[str] = None


# # --------- Auth & Users ---------


# class UserOut(BaseModel):
#     id: int
#     user_hash: str
#     email: str
#     name: Optional[str] = None
#     provider: str
#     journey_day: Optional[int] = None
#     last_journey_date: Optional[date] = None

#     # NEW: onboarding + safety flags exposed to frontend
#     onboarding_complete: bool
#     safety_flag: Optional[int] = None
#     last_phq9_date: Optional[date] = None

#     class Config:
#         orm_mode = True


# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#     user: UserOut


# # --------- Full Intake / Assessments ---------


# class SchemaItemAnswer(BaseModel):
#     schema_key: str          # e.g. "defectiveness_shame"
#     prompt: Optional[str] = None
#     score: int = Field(ge=1, le=6)
#     note: Optional[str] = None


# class Phq9ItemAnswer(BaseModel):
#     question_number: int = Field(ge=1, le=9)
#     prompt: Optional[str] = None
#     score: int = Field(ge=0, le=3)
#     note: Optional[str] = None


# class WeeklyPlanIn(BaseModel):
#     life_area: str
#     life_focus: str
#     actions: List[str]
#     week_plan_text: str


# class IntakeFullIn(BaseModel):
#     """
#     Payload for the entire intake wizard after first Google login.
#     Matches Felix's flow:
#       1) Basic info
#       2) Schema personalization
#       3) Safety screening
#       4) PHQ-9
#       5) Weekly plan + 90-year reflection
#     """
#     # Basic info
#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool = False
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool = False
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     # Safety
#     pregnant_or_planning: bool = False
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool = False
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool = False

#     # Schema items
#     schema_items: List[SchemaItemAnswer]

#     # PHQ-9
#     phq9_items: List[Phq9ItemAnswer]

#     # Weekly plan + 90-year reflection
#     weekly_plan: WeeklyPlanIn
#     good_life_answer: str


# class IntakeFullOut(BaseModel):
#     """
#     Read-back model in case we want to show intake summary later.
#     """
#     id: int
#     user_hash: str
#     created_at: datetime

#     age: Optional[int] = None
#     postal_code: Optional[str] = None
#     gender: Optional[str] = None

#     in_therapy: bool
#     therapy_type: Optional[str] = None
#     therapy_duration: Optional[str] = None

#     on_medication: bool
#     medication_list: Optional[str] = None
#     medication_duration: Optional[str] = None

#     pregnant_or_planning: bool
#     pregnant_notes: Optional[str] = None
#     psychosis_history: bool
#     psychosis_notes: Optional[str] = None
#     privacy_ack: bool

#     life_area: Optional[str] = None
#     life_focus: Optional[str] = None
#     week_actions: List[str]
#     week_plan_text: Optional[str] = None
#     good_life_answer: Optional[str] = None

#     schema_items: List[SchemaItemAnswer]
#     phq9_items: List[Phq9ItemAnswer]

#     class Config:
#         orm_mode = True


# # --------- Journal & Map timeline ---------


# class JournalEntryIn(BaseModel):
#     user_hash: str
#     entry_type: str  # "journal", "insight", "activity", "therapy_future"
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     # IMPORTANT: use Optional[date] here to avoid the runtime error
#     date: Optional[date] = None  # if not provided, defaults to today


# class JournalEntryUpdateIn(BaseModel):
#     """
#     Partial update model for editing a journal / insight / activity entry.
#     All fields are optional; only provided ones are changed.
#     """
#     body: Optional[str] = None
#     title: Optional[str] = None
#     meta: Dict[str, Any] | None = None
#     date: Optional[date] = None


# class JournalEntryOut(BaseModel):
#     id: int
#     user_hash: str
#     entry_type: str
#     body: str
#     title: str | None = None
#     session_id: str | None = None
#     meta: Dict[str, Any] | None = None
#     date: date

#     class Config:
#         orm_mode = True


# class JournalTimelineOut(BaseModel):
#     future: List[JournalEntryOut]
#     today: List[JournalEntryOut]
#     past: List[JournalEntryOut]


# # --------- Settings / Truth Profile ---------


# class TruthProfileIn(BaseModel):
#     bio: str


# class TruthProfileOut(BaseModel):
#     bio: str

from typing import List, Optional, Dict, Any
from datetime import date, datetime

from pydantic import BaseModel, Field


# --------- Intake & Journey generation ---------


class IntakeIn(BaseModel):
    """
    Day-1 intake OR Day-2+ mini check-in.

    All fields are optional so the frontend can submit a sparse payload.
    The /api/journey/generate route will enrich with fallbacks (history/Day-1)
    and apply sensible defaults.
    """
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
    journey_day: Optional[int] = None  # streak-style day selector


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
    script_text: str | None = None  # full script returned in response


# --------- Post-session feedback ---------


class FeedbackIn(BaseModel):
    session_id: str
    chills: int = Field(ge=0, le=3)
    relevance: int = Field(ge=1, le=5)
    emotion_word: str

    # NEW: richer post-session form (optional)
    chills_option: str | None = None       # "yes" | "subtle" | "no"
    chills_detail: str | None = None       # "What sparked that moment?"
    session_insight: str | None = None     # "Any insights from this session?"


# --------- Per-moment Journey events (chills button, insights, etc.) ---------


class JourneyEventIn(BaseModel):
    session_id: str
    user_hash: str | None = None
    event_type: str  # "chills", "insight", "note", etc.
    t_ms: int = Field(ge=0)  # timestamp within audio in milliseconds
    label: str | None = None
    payload: Dict[str, Any] | None = None  # optional extra data (e.g. note text)


# --------- Activity engine (recommendation + tracking) ---------


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
    """Same shape as ActivityOut; kept separate in case we later add scoring fields."""
    pass


class ActivityRecommendationListOut(BaseModel):
    """Used when we want to return multiple recommendations at once."""
    activities: List[ActivityRecommendationOut]


class ActivityListOut(BaseModel):
    activities: List[ActivityOut]


class ActivityStartIn(BaseModel):
    activity_id: int
    user_hash: str
    session_id: str | None = None  # link to Journey session if triggered from a session


class ActivitySwapIn(BaseModel):
    activity_id: int  # the one they swapped away from
    user_hash: str


class ActivityCommitIn(BaseModel):
    """Commit (persist) a specific activity as today's pick."""
    activity_id: int
    user_hash: str


class ActivityCurrentOut(BaseModel):
    activity: Optional[ActivityRecommendationOut] = None


# --------- Home / Today view ---------


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
    # 👇 Expose postal_code so the frontend can pass it into recommendation/generation
    postal_code: Optional[str] = None


# --------- Auth & Users ---------


class UserOut(BaseModel):
    id: int
    user_hash: str
    email: str
    name: Optional[str] = None
    provider: str
    journey_day: Optional[int] = None
    last_journey_date: Optional[date] = None

    # NEW: onboarding + safety flags exposed to frontend
    onboarding_complete: bool
    safety_flag: Optional[int] = None
    last_phq9_date: Optional[date] = None

    class Config:
        orm_mode = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --------- Full Intake / Assessments ---------


class SchemaItemAnswer(BaseModel):
    schema_key: str          # e.g. "defectiveness_shame"
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
    """
    Payload for the entire intake wizard after first Google login.
    Matches Felix's flow:
      1) Basic info
      2) Schema personalization
      3) Safety screening
      4) PHQ-9
      5) Weekly plan + 90-year reflection
    """
    # Basic info
    age: Optional[int] = None
    postal_code: Optional[str] = None
    gender: Optional[str] = None

    in_therapy: bool = False
    therapy_type: Optional[str] = None
    therapy_duration: Optional[str] = None

    on_medication: bool = False
    medication_list: Optional[str] = None
    medication_duration: Optional[str] = None

    # Safety
    pregnant_or_planning: bool = False
    pregnant_notes: Optional[str] = None
    psychosis_history: bool = False
    psychosis_notes: Optional[str] = None
    privacy_ack: bool = False

    # Schema items
    schema_items: List[SchemaItemAnswer]

    # PHQ-9
    phq9_items: List[Phq9ItemAnswer]

    # Weekly plan + 90-year reflection
    weekly_plan: WeeklyPlanIn
    good_life_answer: str


class IntakeFullOut(BaseModel):
    """
    Read-back model in case we want to show intake summary later.
    """
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


# --------- Journal & Map timeline ---------


class JournalEntryIn(BaseModel):
    user_hash: str
    entry_type: str  # "journal", "insight", "activity", "therapy_future"
    body: str
    title: str | None = None
    session_id: str | None = None
    meta: Dict[str, Any] | None = None
    # IMPORTANT: use Optional[date] here to avoid the runtime error
    date: Optional[date] = None  # if not provided, defaults to today


class JournalEntryUpdateIn(BaseModel):
    """
    Partial update model for editing a journal / insight / activity entry.
    All fields are optional; only provided ones are changed.
    """
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


# --------- Settings / Truth Profile ---------


class TruthProfileIn(BaseModel):
    bio: str


class TruthProfileOut(BaseModel):
    bio: str


# ===================== NEW: Profile & Mini-checkins =====================

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


# --- Patch payloads for editing without ids (use keys/numbers) ---

class SchemaItemUpdateByKeyIn(BaseModel):
    schema_key: str
    score: Optional[int] = None
    note: Optional[str] = None


class Phq9ItemUpdateByNumberIn(BaseModel):
    question_number: int = Field(ge=1, le=9)
    score: Optional[int] = None
    note: Optional[str] = None
