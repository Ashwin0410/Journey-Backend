from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user
from app.db import SessionLocal
from app import models, schemas
from app.services import narrative

r = APIRouter()


def db():
  session = SessionLocal()
  try:
      yield session
  finally:
      session.close()


@r.get("/api/today", response_model=schemas.TodaySummaryOut)
def get_today_summary(
    current_user: models.Users = Depends(get_current_user),
    q: Session = Depends(db),
):
    return narrative.build_today_summary(q, current_user)
