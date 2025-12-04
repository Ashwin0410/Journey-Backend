from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import get_current_user

r = APIRouter(prefix="/api/intake", tags=["intake-edit"])


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


def _latest_intake_id(q: Session, user_hash: str) -> int | None:
    row = (
        q.query(models.ClinicalIntake)
        .filter(models.ClinicalIntake.user_hash == user_hash)
        .order_by(models.ClinicalIntake.created_at.desc())
        .first()
    )
    return row.id if row else None


@r.patch("/schema-item", response_model=schemas.SchemaItemAnswer)
def update_schema_item_by_key(
    payload: schemas.SchemaItemUpdateByKeyIn,
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    iid = _latest_intake_id(q, current_user.user_hash)
    if not iid:
        raise HTTPException(status_code=404, detail="No intake found for user")

    row = (
        q.query(models.SchemaItemResponse)
        .filter(
            models.SchemaItemResponse.intake_id == iid,
            models.SchemaItemResponse.user_hash == current_user.user_hash,
            models.SchemaItemResponse.schema_key == payload.schema_key,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Schema item not found")

    data = payload.model_dump(exclude_unset=True)
    if "score" in data and data["score"] is not None:
        row.score = data["score"]
    if "note" in data:
        row.note = data["note"]

    q.commit()
    q.refresh(row)
    return schemas.SchemaItemAnswer(
        schema_key=row.schema_key, prompt=row.prompt, score=row.score, note=row.note
    )


@r.patch("/phq9-item", response_model=schemas.Phq9ItemAnswer)
def update_phq9_item_by_number(
    payload: schemas.Phq9ItemUpdateByNumberIn,
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    iid = _latest_intake_id(q, current_user.user_hash)
    if not iid:
        raise HTTPException(status_code=404, detail="No intake found for user")

    row = (
        q.query(models.Phq9ItemResponse)
        .filter(
            models.Phq9ItemResponse.intake_id == iid,
            models.Phq9ItemResponse.user_hash == current_user.user_hash,
            models.Phq9ItemResponse.question_number == payload.question_number,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="PHQ-9 item not found")

    data = payload.model_dump(exclude_unset=True)
    if "score" in data and data["score"] is not None:
        row.score = data["score"]
    if "note" in data:
        row.note = data["note"]

    q.commit()
    q.refresh(row)
    return schemas.Phq9ItemAnswer(
        question_number=row.question_number, prompt=row.prompt, score=row.score, note=row.note
    )
