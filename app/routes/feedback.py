# feedback.py
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..schemas import FeedbackIn
from ..db import SessionLocal
from ..models import Feedback

r = APIRouter()


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


@r.post("/api/journey/feedback")
def submit(x: FeedbackIn, q: Session = Depends(db)):
    # ISSUE 4 & 5: Serialize chills_moments array to JSON string for storage
    chills_moments_json = None
    if x.chills_moments is not None:
        chills_moments_json = json.dumps(x.chills_moments)
    
    z = Feedback(
        session_id=x.session_id,
        chills=x.chills,
        relevance=x.relevance,
        emotion_word=x.emotion_word,
        chills_option=x.chills_option,
        chills_detail=x.chills_detail,
        session_insight=x.session_insight,
        chills_moments_json=chills_moments_json,  # Save timestamps as JSON
    )
    q.add(z)
    q.commit()
    return {"ok": True}
