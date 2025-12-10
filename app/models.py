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
    provider_id = Column(String, nullable=False) 

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
