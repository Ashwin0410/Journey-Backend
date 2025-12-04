from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import get_current_user

r = APIRouter(prefix="/api/profile", tags=["profile"])


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


def _latest_intake_for_user(q: Session, user_hash: str) -> Optional[models.ClinicalIntake]:
    return (
        q.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )


def _build_intake_out_local(intake: models.ClinicalIntake, q: Session) -> schemas.IntakeFullOut:
    schema_rows: List[models.SchemaItemResponse] = (
        q.query(models.SchemaItemResponse)
        .filter(models.SchemaItemResponse.intake_id == intake.id)
        .all()
    )
    phq_rows: List[models.Phq9ItemResponse] = (
        q.query(models.Phq9ItemResponse)
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


@r.get("/answers", response_model=schemas.ProfileAnswersOut)
def get_profile_answers(
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    user_hash = current_user.user_hash
    intake = _latest_intake_for_user(q, user_hash)

    latest_mc = (
        q.query(models.MiniCheckins)
        .filter(models.MiniCheckins.user_hash == user_hash)
        .order_by(models.MiniCheckins.created_at.desc())
        .first()
    )

    return schemas.ProfileAnswersOut(
        intake=_build_intake_out_local(intake, q) if intake else None,
        latest_mini_checkin=schemas.MiniCheckinOut.model_validate(latest_mc, from_attributes=True)
        if latest_mc
        else None,
    )


@r.get("/checkins", response_model=list[schemas.MiniCheckinOut])
def list_checkins(
    limit: int = Query(20, ge=1, le=100),
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    rows = (
        q.query(models.MiniCheckins)
        .filter(models.MiniCheckins.user_hash == current_user.user_hash)
        .order_by(models.MiniCheckins.created_at.desc())
        .limit(limit)
        .all()
    )
    return [schemas.MiniCheckinOut.model_validate(r, from_attributes=True) for r in rows]


@r.post("/checkins", response_model=schemas.MiniCheckinOut)
def create_checkin(
    payload: schemas.MiniCheckinIn,
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    row = models.MiniCheckins(
        user_hash=current_user.user_hash,
        **payload.model_dump(exclude_unset=True),
    )
    q.add(row)
    q.commit()
    q.refresh(row)
    return schemas.MiniCheckinOut.model_validate(row, from_attributes=True)


@r.patch("/checkins/{checkin_id}", response_model=schemas.MiniCheckinOut)
def update_checkin(
    checkin_id: int = Path(..., ge=1),
    payload: schemas.MiniCheckinIn = ...,
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    row = (
        q.query(models.MiniCheckins)
        .filter(models.MiniCheckins.id == checkin_id, models.MiniCheckins.user_hash == current_user.user_hash)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Mini check-in not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    q.commit()
    q.refresh(row)
    return schemas.MiniCheckinOut.model_validate(row, from_attributes=True)
