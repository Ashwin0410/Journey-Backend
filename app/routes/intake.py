from __future__ import annotations

import json
from typing import List

from datetime import date as date_cls

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import get_current_user

r = APIRouter(prefix="/api/intake", tags=["intake"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
