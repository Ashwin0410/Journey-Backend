from __future__ import annotations

import json
from typing import List, Optional
from datetime import date as date_cls, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import get_current_user

# Import ML predictor service
from app.services.ml_predictor import get_predictor, predict_videos_for_user

r = APIRouter(prefix="/api/intake", tags=["intake"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# INTAKE FLOW CONFIGURATION
# ============================================================================
# 
# The intake flow has been simplified. The following screens are now HIDDEN:
# 
# ❌ HIDDEN: Pre-intake "What's on your mind?" screen (Image 1)
# ❌ HIDDEN: Life area selection screen (Image 2)  
# ❌ HIDDEN: Life focus selection screen
# ❌ HIDDEN: Schema assessment questions
# ❌ HIDDEN: Weekly plan questions
#
# ✅ SHOWN: Demographics (age, gender)
# ✅ SHOWN: PHQ-9 questions
# ✅ SHOWN: ML Personality Questionnaire (9 questions for video recommendation)
#
# The backend endpoints for hidden screens are KEPT for backwards compatibility
# but the frontend will skip them based on the flow-config endpoint response.
#
# ============================================================================


class IntakeFlowConfig(BaseModel):
    """Configuration for which intake screens to show."""
    show_pre_intake: bool = False
    show_life_area: bool = False
    show_life_focus: bool = False
    show_schema_assessment: bool = False
    show_weekly_plan: bool = False
    show_demographics: bool = True
    show_phq9: bool = True
    show_ml_questionnaire: bool = True
    flow_version: str = "v2"  # v1 = old flow with all screens, v2 = simplified


@r.get("/flow-config", response_model=IntakeFlowConfig)
def get_intake_flow_config():
    """
    Get the current intake flow configuration.
    
    Frontend uses this to determine which screens to show/hide during onboarding.
    This allows us to toggle features without frontend code changes.
    """
    return IntakeFlowConfig(
        show_pre_intake=False,      # HIDDEN: "What's on your mind?"
        show_life_area=False,       # HIDDEN: Life area selection
        show_life_focus=False,      # HIDDEN: Life focus selection
        show_schema_assessment=False,  # HIDDEN: Schema questions
        show_weekly_plan=False,     # HIDDEN: Weekly plan
        show_demographics=True,     # SHOWN: Age, gender
        show_phq9=True,            # SHOWN: PHQ-9 assessment
        show_ml_questionnaire=True, # SHOWN: ML personality questions
        flow_version="v2",
    )


# ============================================================================
# INTAKE PROGRESS ENDPOINT (NEW - Issue #3 Fix)
# ============================================================================


class IntakeProgressOut(BaseModel):
    """Output schema for intake progress status."""
    demographics_complete: bool = False
    phq9_complete: bool = False
    ml_questionnaire_complete: bool = False
    onboarding_complete: bool = False
    # Which step to resume from (1=demographics, 2=phq9, 3=ml_questionnaire, 4=done)
    resume_step: int = 1
    # Additional details
    intake_id: Optional[int] = None
    journey_day: Optional[int] = None


@r.get("/progress", response_model=IntakeProgressOut)
def get_intake_progress(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the user's intake progress to determine which step to resume from.
    
    This endpoint is called on page refresh during onboarding to avoid
    forcing users to restart from step 1 if they've already completed
    some steps.
    
    Steps:
    1. Demographics (age, gender, safety questions)
    2. PHQ-9 (9 depression screening questions)
    3. ML Questionnaire (9 personality questions for video personalization)
    4. Done (onboarding complete)
    
    Returns which steps are complete and which step to resume from.
    """
    user_hash = current_user.user_hash
    
    print(f"[intake] Checking progress for user {user_hash}")
    
    # Check if onboarding is already complete
    if current_user.onboarding_complete:
        print(f"[intake] User {user_hash} has already completed onboarding")
        return IntakeProgressOut(
            demographics_complete=True,
            phq9_complete=True,
            ml_questionnaire_complete=True,
            onboarding_complete=True,
            resume_step=4,  # Done
            journey_day=current_user.journey_day,
        )
    
    # Check for existing clinical intake (demographics)
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    demographics_complete = False
    intake_id = None
    
    if intake:
        intake_id = intake.id
        # Demographics is complete if age and gender are set
        if intake.age is not None and intake.gender is not None:
            demographics_complete = True
            print(f"[intake] Demographics complete for user {user_hash}")
    
    # Check for PHQ-9 responses
    phq9_complete = False
    if intake:
        phq9_count = (
            db.query(models.Phq9ItemResponse)
            .filter(models.Phq9ItemResponse.intake_id == intake.id)
            .count()
        )
        # PHQ-9 has 9 questions
        if phq9_count >= 9:
            phq9_complete = True
            print(f"[intake] PHQ-9 complete for user {user_hash}")
    
    # Check for ML questionnaire
    ml_questionnaire_complete = False
    ml_response = (
        db.query(models.MLQuestionnaireResponse)
        .filter(models.MLQuestionnaireResponse.user_hash == user_hash)
        .first()
    )
    if ml_response:
        # ML questionnaire is complete if required fields are set
        if ml_response.dpes_1 is not None and ml_response.neo_ffi_10 is not None:
            ml_questionnaire_complete = True
            print(f"[intake] ML questionnaire complete for user {user_hash}")
    
    # Also check user flag
    if current_user.ml_questionnaire_complete:
        ml_questionnaire_complete = True
    
    # Determine resume step
    resume_step = 1  # Start from demographics
    if demographics_complete:
        resume_step = 2  # Go to PHQ-9
    if demographics_complete and phq9_complete:
        resume_step = 3  # Go to ML questionnaire
    if demographics_complete and phq9_complete and ml_questionnaire_complete:
        resume_step = 4  # Done
    
    print(f"[intake] Progress for user {user_hash}: demographics={demographics_complete}, phq9={phq9_complete}, ml={ml_questionnaire_complete}, resume_step={resume_step}")
    
    return IntakeProgressOut(
        demographics_complete=demographics_complete,
        phq9_complete=phq9_complete,
        ml_questionnaire_complete=ml_questionnaire_complete,
        onboarding_complete=current_user.onboarding_complete or False,
        resume_step=resume_step,
        intake_id=intake_id,
        journey_day=current_user.journey_day,
    )


# ============================================================================
# ML QUESTIONNAIRE SCHEMAS
# ============================================================================

class MLQuestionnaireIn(BaseModel):
    """
    Input schema for ML personality questionnaire.
    
    These 9 questions are used by the ONNX model to predict
    which videos are most likely to induce chills for this user.
    
    Question codes and their scales:
    - DPES_1, DPES_4, DPES_29: 1-7 scale (Dispositional Positive Emotion Scale)
    - NEO-FFI_10, NEO-FFI_14, NEO-FFI_16, NEO-FFI_45, NEO-FFI_46: 1-5 scale
    - KAMF_4_1: 1-7 scale (easily moved/touched)
    """
    # Personality trait questions
    dpes_1: int = Field(
        ge=1, le=7,
        description="It's important to take care of people who are vulnerable (1-7)"
    )
    neo_ffi_10: int = Field(
        ge=1, le=5,
        description="I'm pretty good about pacing myself (1-5)"
    )
    neo_ffi_46: int = Field(
        ge=1, le=5,
        description="I am seldom sad or depressed (1-5)"
    )
    neo_ffi_16: int = Field(
        ge=1, le=5,
        description="I rarely feel lonely or blue (1-5)"
    )
    kamf_4_1: Optional[int] = Field(
        None, ge=1, le=7,
        description="Would you describe yourself as someone who gets easily moved? (1-7)"
    )
    neo_ffi_14: Optional[int] = Field(
        None, ge=1, le=5,
        description="Some people think I'm selfish and egotistical (1-5)"
    )
    dpes_4: Optional[int] = Field(
        None, ge=1, le=7,
        description="I often notice people who need help (1-7)"
    )
    neo_ffi_45: Optional[int] = Field(
        None, ge=1, le=5,
        description="Sometimes I'm not as dependable or reliable (1-5)"
    )
    dpes_29: Optional[int] = Field(
        None, ge=1, le=7,
        description="I find humor in almost everything (1-7)"
    )
    
    # Demographics (can come from existing intake or be provided here)
    age: Optional[str] = Field(
        None,
        description="Age or age range (e.g., '25', '25-34')"
    )
    gender: Optional[str] = Field(
        None,
        description="Gender"
    )
    ethnicity: Optional[str] = Field(
        None,
        description="Ethnicity"
    )
    education: Optional[str] = Field(
        None,
        description="Education level"
    )
    depression_status: Optional[str] = Field(
        None,
        description="Depression status"
    )


class StimulusSuggestionOut(BaseModel):
    """Output schema for a single stimulus suggestion."""
    rank: int
    stimulus_name: str
    stimulus_url: str
    stimulus_description: str
    score: float


class MLQuestionnaireOut(BaseModel):
    """Output schema for ML questionnaire submission."""
    success: bool
    message: str
    questionnaire_id: int
    suggestions: List[StimulusSuggestionOut]
    total_suggestions: int


# ============================================================================
# SIMPLIFIED DEMOGRAPHICS SCHEMA (NEW FLOW)
# ============================================================================

class DemographicsIn(BaseModel):
    """
    Simplified demographics input for the new intake flow.
    Only collects essential information - no life_area, life_focus, schema items, etc.
    """
    age: int = Field(ge=13, le=120, description="User's age in years")
    gender: str = Field(description="User's gender")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    
    # Safety questions (kept for clinical safety)
    in_therapy: bool = Field(default=False)
    on_medication: bool = Field(default=False)
    psychosis_history: bool = Field(default=False)
    pregnant_or_planning: bool = Field(default=False)


class DemographicsOut(BaseModel):
    """Output schema for demographics submission."""
    success: bool
    message: str
    intake_id: int


class Phq9ItemIn(BaseModel):
    """Single PHQ-9 question response."""
    question_number: int = Field(ge=1, le=9)
    score: int = Field(ge=0, le=3)


class Phq9SubmitIn(BaseModel):
    """PHQ-9 questionnaire submission."""
    items: List[Phq9ItemIn] = Field(min_length=9, max_length=9)


class Phq9Out(BaseModel):
    """Output schema for PHQ-9 submission."""
    success: bool
    message: str
    total_score: int
    safety_flag: int  # 0=normal, 1=elevated, 2=high risk (Q9 > 0)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _build_intake_out(intake: models.ClinicalIntake, db: Session) -> schemas.IntakeFullOut:
    schema_rows: List[models.SchemaItemResponse] = (
        db.query(models.SchemaItemResponse)
        .filter(models.SchemaItemResponse.intake_id == intake.id)
        .all()
    )
    phq_rows: List[models.Phq9ItemResponse] = (
        db.query(models.Phq9ItemResponse)
        .filter(models.Phq9ItemResponse.intake_id == intake.id)
        .all()
    )

    week_actions: List[str] = []
    try:
        if intake.week_actions_json:
            week_actions = json.loads(intake.week_actions_json)
    except Exception:
        week_actions = []

    return schemas.IntakeFullOut(
        id=intake.id,
        user_hash=intake.user_hash,
        created_at=intake.created_at,
        pre_intake_text=intake.pre_intake_text,
        age=intake.age,
        postal_code=intake.postal_code,
        gender=intake.gender,
        in_therapy=intake.in_therapy,
        therapy_type=intake.therapy_type,
        therapy_duration=intake.therapy_duration,
        on_medication=intake.on_medication,
        medication_list=intake.medication_list,
        medication_duration=intake.medication_duration,
        pregnant_or_planning=intake.pregnant_or_planning,
        pregnant_notes=intake.pregnant_notes,
        psychosis_history=intake.psychosis_history,
        psychosis_notes=intake.psychosis_notes,
        privacy_ack=intake.privacy_ack,
        life_area=intake.life_area,
        life_focus=intake.life_focus,
        week_actions=week_actions,
        week_plan_text=intake.week_plan_text,
        good_life_answer=intake.good_life_answer,
        schema_items=[
            schemas.SchemaItemAnswer(
                schema_key=s.schema_key,
                prompt=s.prompt,
                score=s.score,
                note=s.note,
            )
            for s in schema_rows
        ],
        phq9_items=[
            schemas.Phq9ItemAnswer(
                question_number=p.question_number,
                prompt=p.prompt,
                score=p.score,
                note=p.note,
            )
            for p in phq_rows
        ],
    )


# ============================================================================
# PHQ-9 QUESTION PROMPTS (for reference)
# ============================================================================

PHQ9_PROMPTS = [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
    "Trouble concentrating on things, such as reading the newspaper or watching television",
    "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual",
    "Thoughts that you would be better off dead or of hurting yourself in some way",
]


# ============================================================================
# NEW SIMPLIFIED INTAKE ENDPOINTS (V2 FLOW)
# ============================================================================

@r.post("/demographics", response_model=DemographicsOut)
def submit_demographics(
    payload: DemographicsIn,
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit basic demographics for the simplified V2 intake flow.
    
    This is the first step in the new flow:
    1. Demographics (this endpoint)
    2. PHQ-9 questions
    3. ML Personality Questionnaire
    
    NOTE: This does NOT set onboarding_complete=True. That happens
    after the ML questionnaire is submitted.
    """
    user_hash = current_user.user_hash
    
    print(f"[intake] Demographics submitted by user {user_hash}")
    
    # Check if there's an existing intake to update
    existing_intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    if existing_intake:
        # Update existing intake
        intake = existing_intake
        intake.age = payload.age
        intake.gender = payload.gender
        intake.postal_code = payload.postal_code
        intake.in_therapy = payload.in_therapy
        intake.on_medication = payload.on_medication
        intake.psychosis_history = payload.psychosis_history
        intake.pregnant_or_planning = payload.pregnant_or_planning
        db.commit()
        db.refresh(intake)
        print(f"[intake] Updated existing intake id={intake.id}")
    else:
        # Create new intake
        intake = models.ClinicalIntake(
            user_hash=user_hash,
            age=payload.age,
            gender=payload.gender,
            postal_code=payload.postal_code,
            in_therapy=payload.in_therapy,
            on_medication=payload.on_medication,
            psychosis_history=payload.psychosis_history,
            pregnant_or_planning=payload.pregnant_or_planning,
        )
        db.add(intake)
        db.commit()
        db.refresh(intake)
        print(f"[intake] Created new intake id={intake.id}")
    
    return DemographicsOut(
        success=True,
        message="Demographics saved successfully",
        intake_id=intake.id,
    )


@r.post("/phq9", response_model=Phq9Out)
def submit_phq9(
    payload: Phq9SubmitIn,
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit PHQ-9 questionnaire responses.
    
    This is the second step in the new V2 flow:
    1. Demographics
    2. PHQ-9 questions (this endpoint)
    3. ML Personality Questionnaire
    
    The PHQ-9 is a 9-question depression screening tool.
    Each question is scored 0-3 (Not at all, Several days, More than half, Nearly every day).
    
    Safety flag logic:
    - 0 = Normal
    - 1 = Elevated (total score >= 15)
    - 2 = High risk (question 9 score > 0, indicates self-harm thoughts)
    """
    user_hash = current_user.user_hash
    
    print(f"[intake] PHQ-9 submitted by user {user_hash}")
    
    # Get existing intake
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    
    if not intake:
        # Create a minimal intake if none exists (edge case)
        intake = models.ClinicalIntake(user_hash=user_hash)
        db.add(intake)
        db.commit()
        db.refresh(intake)
        print(f"[intake] Created minimal intake for PHQ-9, id={intake.id}")
    
    # Delete any existing PHQ-9 responses for this intake
    db.query(models.Phq9ItemResponse).filter(
        models.Phq9ItemResponse.intake_id == intake.id
    ).delete()
    db.commit()
    
    # Store new PHQ-9 responses
    total_score = 0
    q9_score = 0
    
    for item in payload.items:
        prompt = PHQ9_PROMPTS[item.question_number - 1] if item.question_number <= len(PHQ9_PROMPTS) else ""
        
        db.add(models.Phq9ItemResponse(
            intake_id=intake.id,
            user_hash=user_hash,
            question_number=item.question_number,
            prompt=prompt,
            score=item.score,
            is_suicide_item=(item.question_number == 9),
        ))
        
        total_score += item.score
        if item.question_number == 9:
            q9_score = item.score
    
    # Calculate safety flag
    safety_flag = 0
    if q9_score > 0:
        safety_flag = 2  # High risk - self-harm thoughts indicated
    elif total_score >= 15:
        safety_flag = 1  # Elevated depression score
    
    # Update user safety flag
    user = db.merge(current_user)
    user.safety_flag = safety_flag
    user.last_phq9_date = date_cls.today()
    db.commit()
    
    print(f"[intake] PHQ-9 saved: total_score={total_score}, safety_flag={safety_flag}")
    
    return Phq9Out(
        success=True,
        message="PHQ-9 responses saved successfully",
        total_score=total_score,
        safety_flag=safety_flag,
    )


# ============================================================================
# LEGACY ENDPOINTS (KEPT FOR BACKWARDS COMPATIBILITY)
# ============================================================================

@r.post("/pre-intake", response_model=schemas.PreIntakeOut)
def submit_pre_intake(
    payload: schemas.PreIntakeIn,
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Store the pre-intake 'on your mind' text.
    Creates a new ClinicalIntake record with just the pre_intake_text,
    or updates an existing incomplete one.
    
    ⚠️ HIDDEN IN V2 FLOW: This endpoint is hidden in the new simplified flow
    but kept for backwards compatibility. The frontend will skip this screen
    based on the /flow-config response.
    """
    user_hash = current_user.user_hash

    # Check if there's an existing intake for this user that we can update
    # (in case they go back and forth during onboarding)
    existing_intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )

    if existing_intake:
        # Update existing intake with pre_intake_text
        existing_intake.pre_intake_text = payload.pre_intake_text
        db.commit()
    else:
        # Create a new intake record with just the pre_intake_text
        intake = models.ClinicalIntake(
            user_hash=user_hash,
            pre_intake_text=payload.pre_intake_text,
        )
        db.add(intake)
        db.commit()

    return schemas.PreIntakeOut(
        success=True,
        message="Pre-intake response saved successfully"
    )


@r.post("/full", response_model=schemas.IntakeFullOut)
def submit_full_intake(
    payload: schemas.IntakeFullIn,
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit full intake with demographics, PHQ-9, schema items, weekly plan.
    
    ⚠️ LEGACY ENDPOINT: This is the old full intake endpoint that includes
    all screens (life_area, life_focus, schema assessment, weekly plan).
    
    In the V2 flow, use these endpoints instead:
    1. POST /api/intake/demographics
    2. POST /api/intake/phq9
    3. POST /api/intake/ml-questionnaire
    
    This endpoint is kept for backwards compatibility.
    """

    user = current_user
    user_hash = user.user_hash

    # Check if there's an existing intake (from pre-intake) to update
    existing_intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )

    if existing_intake and existing_intake.age is None:
        # Update the existing pre-intake record with full intake data
        intake = existing_intake
        intake.pre_intake_text = payload.pre_intake_text if payload.pre_intake_text else intake.pre_intake_text
        intake.age = payload.age
        intake.postal_code = payload.postal_code
        intake.gender = payload.gender
        intake.in_therapy = payload.in_therapy
        intake.therapy_type = payload.therapy_type
        intake.therapy_duration = payload.therapy_duration
        intake.on_medication = payload.on_medication
        intake.medication_list = payload.medication_list
        intake.medication_duration = payload.medication_duration
        intake.pregnant_or_planning = payload.pregnant_or_planning
        intake.pregnant_notes = payload.pregnant_notes
        intake.psychosis_history = payload.psychosis_history
        intake.psychosis_notes = payload.psychosis_notes
        intake.privacy_ack = payload.privacy_ack
        intake.life_area = payload.weekly_plan.life_area
        intake.life_focus = payload.weekly_plan.life_focus
        intake.week_actions_json = json.dumps(payload.weekly_plan.actions)
        intake.week_plan_text = payload.weekly_plan.week_plan_text
        intake.good_life_answer = payload.good_life_answer
        db.commit()
        db.refresh(intake)
    else:
        # Create a new intake record
        intake = models.ClinicalIntake(
            user_hash=user_hash,
            pre_intake_text=payload.pre_intake_text,
            age=payload.age,
            postal_code=payload.postal_code,
            gender=payload.gender,
            in_therapy=payload.in_therapy,
            therapy_type=payload.therapy_type,
            therapy_duration=payload.therapy_duration,
            on_medication=payload.on_medication,
            medication_list=payload.medication_list,
            medication_duration=payload.medication_duration,
            pregnant_or_planning=payload.pregnant_or_planning,
            pregnant_notes=payload.pregnant_notes,
            psychosis_history=payload.psychosis_history,
            psychosis_notes=payload.psychosis_notes,
            privacy_ack=payload.privacy_ack,
            life_area=payload.weekly_plan.life_area,
            life_focus=payload.weekly_plan.life_focus,
            week_actions_json=json.dumps(payload.weekly_plan.actions),
            week_plan_text=payload.weekly_plan.week_plan_text,
            good_life_answer=payload.good_life_answer,
        )

        db.add(intake)
        db.commit()
        db.refresh(intake)

    for item in payload.schema_items:
        db.add(
            models.SchemaItemResponse(
                intake_id=intake.id,
                user_hash=user_hash,
                schema_key=item.schema_key,
                prompt=item.prompt,
                score=item.score,
                note=item.note,
            )
        )


    for item in payload.phq9_items:
        db.add(
            models.Phq9ItemResponse(
                intake_id=intake.id,
                user_hash=user_hash,
                question_number=item.question_number,
                prompt=item.prompt,
                score=item.score,
                note=item.note,
                is_suicide_item=(item.question_number == 9),
            )
        )

   
    total_score = sum(i.score for i in payload.phq9_items)

    q9_score = 0
    for i in payload.phq9_items:
        if i.question_number == 9:
            q9_score = i.score
            break

    safety_flag = 0
    if q9_score > 0:
        safety_flag = 2
    elif total_score >= 15:
        safety_flag = 1


    user = db.merge(user)

    user.safety_flag = safety_flag
    user.last_phq9_date = date_cls.today()
    user.onboarding_complete = True  # ← THE VALUE THE FRONTEND NEEDS

    db.commit()       # save all
    db.refresh(user)  # ensure updated user is returned

    return _build_intake_out(intake, db)


@r.get("/me", response_model=schemas.IntakeFullOut | None)
def get_my_intake(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's intake data."""
    user_hash = current_user.user_hash
    intake = (
        db.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    if not intake:
        return None

    return _build_intake_out(intake, db)


# ============================================================================
# ML QUESTIONNAIRE ENDPOINT
# ============================================================================

@r.post("/ml-questionnaire", response_model=MLQuestionnaireOut)
def submit_ml_questionnaire(
    payload: MLQuestionnaireIn,
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit ML personality questionnaire and get personalized video recommendations.
    
    This is the FINAL step in the V2 intake flow:
    1. Demographics
    2. PHQ-9 questions
    3. ML Personality Questionnaire (this endpoint)
    
    This endpoint:
    1. Stores the user's questionnaire responses
    2. Runs the ONNX ML model to predict chills probability for 40 videos
    3. Stores the top 10 video suggestions for this user
    4. Marks onboarding as complete
    5. Returns the ranked video suggestions
    
    The user will watch the rank #1 video on Day 1, rank #2 on Day 2, etc.
    """
    user_hash = current_user.user_hash
    
    print(f"[intake] ========== ML QUESTIONNAIRE START ==========")
    print(f"[intake] ML questionnaire submitted by user {user_hash}")
    
    # =========================================================================
    # STEP 1: Get demographics from existing intake or payload
    # =========================================================================
    
    age = payload.age
    gender = payload.gender
    
    # Try to get demographics from existing clinical intake if not provided
    if not age or not gender:
        existing_intake = (
            db.query(models.ClinicalIntake)
            .filter(models.ClinicalIntake.user_hash == user_hash)
            .order_by(models.ClinicalIntake.created_at.desc())
            .first()
        )
        if existing_intake:
            if not age and existing_intake.age:
                age = str(existing_intake.age)
            if not gender and existing_intake.gender:
                gender = existing_intake.gender
    
    print(f"[intake] Demographics: age={age}, gender={gender}")
    
    # =========================================================================
    # STEP 2: Store questionnaire responses
    # =========================================================================
    
    # Check if user already has a questionnaire response (update instead of create)
    existing_response = (
        db.query(models.MLQuestionnaireResponse)
        .filter(models.MLQuestionnaireResponse.user_hash == user_hash)
        .first()
    )
    
    if existing_response:
        # Update existing response
        existing_response.dpes_1 = payload.dpes_1
        existing_response.neo_ffi_10 = payload.neo_ffi_10
        existing_response.neo_ffi_46 = payload.neo_ffi_46
        existing_response.neo_ffi_16 = payload.neo_ffi_16
        existing_response.kamf_4_1 = payload.kamf_4_1
        existing_response.neo_ffi_14 = payload.neo_ffi_14
        existing_response.dpes_4 = payload.dpes_4
        existing_response.neo_ffi_45 = payload.neo_ffi_45
        existing_response.dpes_29 = payload.dpes_29
        existing_response.age = age
        existing_response.gender = gender
        existing_response.ethnicity = payload.ethnicity
        existing_response.education = payload.education
        existing_response.depression_status = payload.depression_status
        existing_response.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_response)
        questionnaire = existing_response
        
        print(f"[intake] Updated existing ML questionnaire id={questionnaire.id}")
        
        # Delete old suggestions before generating new ones
        db.query(models.StimuliSuggestion).filter(
            models.StimuliSuggestion.user_hash == user_hash
        ).delete()
        db.commit()
    else:
        # Create new questionnaire response
        questionnaire = models.MLQuestionnaireResponse(
            user_hash=user_hash,
            dpes_1=payload.dpes_1,
            neo_ffi_10=payload.neo_ffi_10,
            neo_ffi_46=payload.neo_ffi_46,
            neo_ffi_16=payload.neo_ffi_16,
            kamf_4_1=payload.kamf_4_1,
            neo_ffi_14=payload.neo_ffi_14,
            dpes_4=payload.dpes_4,
            neo_ffi_45=payload.neo_ffi_45,
            dpes_29=payload.dpes_29,
            age=age,
            gender=gender,
            ethnicity=payload.ethnicity,
            education=payload.education,
            depression_status=payload.depression_status,
            created_at=datetime.utcnow(),
        )
        db.add(questionnaire)
        db.commit()
        db.refresh(questionnaire)
        
        print(f"[intake] Created new ML questionnaire id={questionnaire.id}")
    
    # =========================================================================
    # STEP 3: Run ML prediction
    # =========================================================================
    
    # Build answers dict for ML predictor
    answers = {
        "DPES_1": payload.dpes_1,
        "NEO-FFI_10": payload.neo_ffi_10,
        "NEO-FFI_46": payload.neo_ffi_46,
        "NEO-FFI_16": payload.neo_ffi_16,
        "KAMF_4_1": payload.kamf_4_1,
        "NEO-FFI_14": payload.neo_ffi_14,
        "DPES_4": payload.dpes_4,
        "NEO-FFI_45": payload.neo_ffi_45,
        "DPES_29": payload.dpes_29,
        "Age": age,
        "Gender": gender,
        "Ethnicity": payload.ethnicity,
        "Education": payload.education,
        "Depression": payload.depression_status,
    }
    
    print(f"[intake] Calling ML predictor with answers: {answers}")
    
    # Get predictor and run inference
    try:
        predictor = get_predictor()
        
        print(f"[intake] Predictor initialized: {predictor.is_initialized}, error: {predictor.error_message}")
        
        if not predictor.is_initialized:
            raise HTTPException(
                status_code=500,
                detail=f"ML predictor not initialized: {predictor.error_message}"
            )
        
        # Get top 10 video recommendations (enough for 10 days)
        predictions = predictor.predict_top_k(answers, k=10)
        
        print(f"[intake] ML predictor returned {len(predictions)} predictions")
        for i, pred in enumerate(predictions):
            print(f"[intake]   #{i+1}: {pred['stimulus_name']} (score={pred['score']:.4f})")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[intake] ML prediction error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"ML prediction failed: {str(e)}"
        )
    
    # =========================================================================
    # STEP 4: Store suggestions in database
    # =========================================================================
    
    suggestions_out = []
    
    for pred in predictions:
        suggestion = models.StimuliSuggestion(
            user_hash=user_hash,
            questionnaire_id=questionnaire.id,
            stimulus_rank=pred["rank"],
            stimulus_name=pred["stimulus_name"],
            stimulus_url=pred["stimulus_url"],
            stimulus_description=pred.get("stimulus_description", ""),
            score=pred["score"],
            created_at=datetime.utcnow(),
        )
        db.add(suggestion)
        
        suggestions_out.append(StimulusSuggestionOut(
            rank=pred["rank"],
            stimulus_name=pred["stimulus_name"],
            stimulus_url=pred["stimulus_url"],
            stimulus_description=pred.get("stimulus_description", ""),
            score=pred["score"],
        ))
    
    db.commit()
    
    print(f"[intake] Stored {len(suggestions_out)} video suggestions for user {user_hash}")
    
    # =========================================================================
    # STEP 5: Mark user as having completed ML questionnaire AND onboarding
    # =========================================================================
    
    # Update user record to indicate ML questionnaire is complete
    user = db.merge(current_user)
    user.ml_questionnaire_complete = True
    user.onboarding_complete = True  # V2 flow: ML questionnaire completion = onboarding complete
    
    # Initialize journey day if not set
    if user.journey_day is None:
        user.journey_day = 1
    
    db.commit()
    
    print(f"[intake] User {user_hash} onboarding_complete={user.onboarding_complete}, ml_questionnaire_complete={user.ml_questionnaire_complete}, journey_day={user.journey_day}")
    print(f"[intake] ========== ML QUESTIONNAIRE END ==========")
    
    return MLQuestionnaireOut(
        success=True,
        message="ML questionnaire submitted successfully. Video recommendations generated.",
        questionnaire_id=questionnaire.id,
        suggestions=suggestions_out,
        total_suggestions=len(suggestions_out),
    )


@r.get("/ml-questionnaire/me")
def get_my_ml_questionnaire(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current user's ML questionnaire responses and video suggestions.
    """
    user_hash = current_user.user_hash
    
    print(f"[intake] Getting ML questionnaire for user {user_hash}")
    
    # Get questionnaire response
    questionnaire = (
        db.query(models.MLQuestionnaireResponse)
        .filter(models.MLQuestionnaireResponse.user_hash == user_hash)
        .first()
    )
    
    if not questionnaire:
        print(f"[intake] No ML questionnaire found for user {user_hash}")
        return {
            "has_questionnaire": False,
            "questionnaire": None,
            "suggestions": [],
        }
    
    # Get suggestions
    suggestions = (
        db.query(models.StimuliSuggestion)
        .filter(models.StimuliSuggestion.user_hash == user_hash)
        .order_by(models.StimuliSuggestion.stimulus_rank.asc())
        .all()
    )
    
    print(f"[intake] Found questionnaire id={questionnaire.id} with {len(suggestions)} suggestions")
    
    return {
        "has_questionnaire": True,
        "questionnaire": {
            "id": questionnaire.id,
            "dpes_1": questionnaire.dpes_1,
            "neo_ffi_10": questionnaire.neo_ffi_10,
            "neo_ffi_46": questionnaire.neo_ffi_46,
            "neo_ffi_16": questionnaire.neo_ffi_16,
            "kamf_4_1": questionnaire.kamf_4_1,
            "neo_ffi_14": questionnaire.neo_ffi_14,
            "dpes_4": questionnaire.dpes_4,
            "neo_ffi_45": questionnaire.neo_ffi_45,
            "dpes_29": questionnaire.dpes_29,
            "age": questionnaire.age,
            "gender": questionnaire.gender,
            "created_at": questionnaire.created_at,
        },
        "suggestions": [
            {
                "rank": s.stimulus_rank,
                "stimulus_name": s.stimulus_name,
                "stimulus_url": s.stimulus_url,
                "stimulus_description": s.stimulus_description,
                "score": s.score,
            }
            for s in suggestions
        ],
    }


@r.get("/video-for-today")
def get_video_for_today(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get today's video recommendation based on user's journey day.
    
    Day 1 = rank #1 video, Day 2 = rank #2 video, etc.
    If journey_day > 10 (we only have 10 suggestions), it wraps around.
    """
    user_hash = current_user.user_hash
    journey_day = current_user.journey_day or 1
    
    print(f"[intake] Getting video for today: user={user_hash}, journey_day={journey_day}")
    
    # Wrap around if we've gone past 10 days
    effective_rank = ((journey_day - 1) % 10) + 1
    
    print(f"[intake] Effective rank for day {journey_day} = {effective_rank}")
    
    # Get the suggestion for this day
    suggestion = (
        db.query(models.StimuliSuggestion)
        .filter(
            models.StimuliSuggestion.user_hash == user_hash,
            models.StimuliSuggestion.stimulus_rank == effective_rank,
        )
        .first()
    )
    
    if not suggestion:
        print(f"[intake] No suggestion found for rank {effective_rank}, trying rank 1")
        # Try to get any suggestion (fallback to rank 1)
        suggestion = (
            db.query(models.StimuliSuggestion)
            .filter(models.StimuliSuggestion.user_hash == user_hash)
            .order_by(models.StimuliSuggestion.stimulus_rank.asc())
            .first()
        )
    
    if not suggestion:
        print(f"[intake] No video suggestions found for user {user_hash}")
        return {
            "has_video": False,
            "message": "No video suggestions found. Please complete the ML questionnaire first.",
            "video": None,
        }
    
    print(f"[intake] Returning video: {suggestion.stimulus_name} (rank={suggestion.stimulus_rank})")
    
    return {
        "has_video": True,
        "journey_day": journey_day,
        "video": {
            "rank": suggestion.stimulus_rank,
            "stimulus_name": suggestion.stimulus_name,
            "stimulus_url": suggestion.stimulus_url,
            "stimulus_description": suggestion.stimulus_description,
            "score": suggestion.score,
        },
    }
