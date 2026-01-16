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
# ML QUESTIONNAIRE SCHEMAS
# ============================================================================

class MLQuestionnaireIn(BaseModel):
    """
    Input schema for ML personality questionnaire.
    
    These 10 questions are used by the ONNX model to predict
    which videos are most likely to induce chills for this user.
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
# EXISTING HELPER FUNCTIONS
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
# EXISTING ENDPOINTS (UNCHANGED)
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
    
    NOTE: This endpoint is HIDDEN in the new flow but kept for backwards compatibility.
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
    
    NOTE: Schema assessment and weekly plan portions are HIDDEN in the new flow
    but this endpoint is kept for backwards compatibility.
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
# NEW ML QUESTIONNAIRE ENDPOINT
# ============================================================================

@r.post("/ml-questionnaire", response_model=MLQuestionnaireOut)
def submit_ml_questionnaire(
    payload: MLQuestionnaireIn,
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit ML personality questionnaire and get personalized video recommendations.
    
    This endpoint:
    1. Stores the user's questionnaire responses
    2. Runs the ONNX ML model to predict chills probability for 40 videos
    3. Stores the top video suggestions for this user
    4. Returns the ranked video suggestions
    
    The user will watch the rank #1 video on Day 1, rank #2 on Day 2, etc.
    """
    user_hash = current_user.user_hash
    
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
                age = existing_intake.age
            if not gender and existing_intake.gender:
                gender = existing_intake.gender
    
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
    
    # Get predictor and run inference
    try:
        predictor = get_predictor()
        
        if not predictor.is_initialized:
            raise HTTPException(
                status_code=500,
                detail=f"ML predictor not initialized: {predictor.error_message}"
            )
        
        # Get top 10 video recommendations (enough for 10 days)
        predictions = predictor.predict_top_k(answers, k=10)
        
        print(f"[intake] ML predictor returned {len(predictions)} predictions")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[intake] ML prediction error: {e}")
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
    # STEP 5: Mark user as having completed ML questionnaire
    # =========================================================================
    
    # Update user record to indicate ML questionnaire is complete
    user = db.merge(current_user)
    user.ml_questionnaire_complete = True
    db.commit()
    
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
    
    # Get questionnaire response
    questionnaire = (
        db.query(models.MLQuestionnaireResponse)
        .filter(models.MLQuestionnaireResponse.user_hash == user_hash)
        .first()
    )
    
    if not questionnaire:
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
    """
    user_hash = current_user.user_hash
    journey_day = current_user.journey_day or 1
    
    # Get the suggestion for this day
    suggestion = (
        db.query(models.StimuliSuggestion)
        .filter(
            models.StimuliSuggestion.user_hash == user_hash,
            models.StimuliSuggestion.stimulus_rank == journey_day,
        )
        .first()
    )
    
    if not suggestion:
        # Try to get any suggestion (fallback to rank 1)
        suggestion = (
            db.query(models.StimuliSuggestion)
            .filter(models.StimuliSuggestion.user_hash == user_hash)
            .order_by(models.StimuliSuggestion.stimulus_rank.asc())
            .first()
        )
    
    if not suggestion:
        return {
            "has_video": False,
            "message": "No video suggestions found. Please complete the ML questionnaire first.",
            "video": None,
        }
    
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
