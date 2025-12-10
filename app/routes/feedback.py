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
    z = Feedback(
        session_id=x.session_id,
        chills=x.chills,
        relevance=x.relevance,
        emotion_word=x.emotion_word,
        chills_option=x.chills_option,
        chills_detail=x.chills_detail,
        session_insight=x.session_insight,
        # ADDED: Extended feedback fields for Day 2+ personalization (Issue 10)
        tell_us_more=x.tell_us_more,
        feeling_after=x.feeling_after,
        body_after=x.body_after,
        energy_after=x.energy_after,
        goal_reflection=x.goal_reflection,
        what_helped=x.what_helped,
        what_was_hard=x.what_was_hard,
    )
    q.add(z)
    q.commit()
    return {"ok": True}


# ADDED: Endpoint to retrieve latest feedback for a user (Issue 10)
# This will be used by journey generation to personalize Day 2+ content
@r.get("/api/journey/feedback/latest/{user_id}")
def get_latest_feedback(user_id: int, q: Session = Depends(db)):
    """
    Get the most recent feedback from a user for use in generating
    personalized Day 2+ journeys.
    """
    from ..models import JourneySession
    
    # Find the most recent feedback for this user's sessions
    latest = (
        q.query(Feedback)
        .join(JourneySession, Feedback.session_id == JourneySession.id)
        .filter(JourneySession.user_id == user_id)
        .order_by(Feedback.id.desc())
        .first()
    )
    
    if not latest:
        return {"found": False, "feedback": None}
    
    return {
        "found": True,
        "feedback": {
            "session_id": latest.session_id,
            "chills": latest.chills,
            "relevance": latest.relevance,
            "emotion_word": latest.emotion_word,
            "chills_option": latest.chills_option,
            "chills_detail": latest.chills_detail,
            "session_insight": latest.session_insight,
            "tell_us_more": latest.tell_us_more,
            "feeling_after": latest.feeling_after,
            "body_after": latest.body_after,
            "energy_after": latest.energy_after,
            "goal_reflection": latest.goal_reflection,
            "what_helped": latest.what_helped,
            "what_was_hard": latest.what_was_hard,
        }
    }
