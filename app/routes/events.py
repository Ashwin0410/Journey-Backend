from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import json

from ..db import SessionLocal
from ..schemas import JourneyEventIn
from ..models import JourneyEvent

r = APIRouter()


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


@r.post("/api/journey/event")
def log_event(x: JourneyEventIn, q: Session = Depends(db)):
    """
    Log a single Journey event (e.g. chills button press, insight moment, note).

    Expected body:
    {
      "session_id": "...",
      "event_type": "chills" | "insight" | "note" | ...,
      "t_ms": 43210,
      "user_hash": "optional",
      "label": "optional short label",
      "payload": { ... optional JSON payload ... }
    }
    """
    payload_json = None
    if x.payload is not None:
        payload_json = json.dumps(x.payload, ensure_ascii=False)

    row = JourneyEvent(
        session_id=x.session_id,
        user_hash=x.user_hash or "",
        event_type=x.event_type,
        t_ms=x.t_ms,
        label=x.label or "",
        payload_json=payload_json,
    )
    q.add(row)
    q.commit()

    return {"ok": True}
