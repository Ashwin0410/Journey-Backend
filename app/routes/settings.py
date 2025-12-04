from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user
from ..db import SessionLocal
from .. import models, schemas

r = APIRouter()


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


def _truth_profile_key(user_hash: str) -> str:
    return f"truth_profile:{user_hash}"


@r.get("/api/settings/truth-profile", response_model=schemas.TruthProfileOut)
def get_truth_profile(
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):

    key = _truth_profile_key(current_user.user_hash)
    row = q.query(models.KV).filter(models.KV.k == key).first()

    bio = ""
    if row and row.v:
        try:
            data = json.loads(row.v)
            if isinstance(data, dict):
                bio = str(data.get("bio", "") or "")
            else:
                bio = str(row.v)
        except Exception:
            bio = str(row.v)

    return schemas.TruthProfileOut(bio=bio)


@r.post("/api/settings/truth-profile", response_model=schemas.TruthProfileOut)
def set_truth_profile(
    payload: schemas.TruthProfileIn,
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):

    key = _truth_profile_key(current_user.user_hash)
    row = q.query(models.KV).filter(models.KV.k == key).first()
    value = json.dumps({"bio": payload.bio})

    if row:
        row.v = value
    else:
        row = models.KV(k=key, v=value)
        q.add(row)

    q.commit()
    return schemas.TruthProfileOut(bio=payload.bio)
