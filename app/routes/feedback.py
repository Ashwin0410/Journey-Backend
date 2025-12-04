# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
# from ..schemas import FeedbackIn
# from ..db import SessionLocal
# from ..models import Feedback

# r = APIRouter()

# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()

# @r.post("/api/journey/feedback")
# def submit(x: FeedbackIn, q: Session = Depends(db)):
#     z = Feedback(session_id=x.session_id, chills=x.chills, relevance=x.relevance, emotion_word=x.emotion_word)
#     q.add(z); q.commit()
#     return {"ok": True}



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
    )
    q.add(z)
    q.commit()
    return {"ok": True}
