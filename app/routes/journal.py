from __future__ import annotations

import json
from datetime import datetime, date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import JournalEntries
from ..schemas import (
    JournalEntryIn,
    JournalEntryOut,
    JournalTimelineOut,
    JournalEntryUpdateIn,
)

r = APIRouter()


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


def _row_to_schema(row: JournalEntries) -> JournalEntryOut:
    try:
        meta = json.loads(row.meta_json) if row.meta_json else None
        if meta is not None and not isinstance(meta, dict):
            meta = None
    except Exception:
        meta = None

    return JournalEntryOut(
        id=row.id,
        user_hash=row.user_hash,
        entry_type=row.entry_type,
        body=row.body,
        title=row.title,
        session_id=row.session_id,
        meta=meta,
        date=row.date,
    )


@r.post("/api/journey/journal", response_model=JournalEntryOut)
def create_journal_entry(x: JournalEntryIn, q: Session = Depends(db)):
    entry_date: date = x.date or datetime.utcnow().date()

    meta_json = json.dumps(x.meta) if x.meta is not None else None

    row = JournalEntries(
        user_hash=x.user_hash,
        session_id=x.session_id,
        entry_type=x.entry_type,
        title=x.title,
        body=x.body,
        meta_json=meta_json,
        date=entry_date,
    )
    q.add(row)
    q.commit()
    q.refresh(row)

    return _row_to_schema(row)


@r.get("/api/journey/journal/timeline", response_model=JournalTimelineOut)
def get_journal_timeline(
    user_hash: str = Query(...),
    q: Session = Depends(db),
):
    today = datetime.utcnow().date()

    rows: List[JournalEntries] = (
        q.query(JournalEntries)
        .filter(JournalEntries.user_hash == user_hash)
        .order_by(JournalEntries.date.asc(), JournalEntries.id.asc())
        .all()
    )

    future: List[JournalEntryOut] = []
    today_list: List[JournalEntryOut] = []
    past: List[JournalEntryOut] = []

    for row in rows:
        item = _row_to_schema(row)
        if item.date > today:
            future.append(item)
        elif item.date == today:
            today_list.append(item)
        else:
            past.append(item)


    past.sort(key=lambda e: (e.date, e.id), reverse=True)

    return JournalTimelineOut(future=future, today=today_list, past=past)


@r.patch("/api/journey/journal/{entry_id}", response_model=JournalEntryOut)
def update_journal_entry(
    entry_id: int,
    x: JournalEntryUpdateIn,
    q: Session = Depends(db),
):
    row = q.query(JournalEntries).filter(JournalEntries.id == entry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if x.title is not None:
        row.title = x.title
    if x.body is not None:
        row.body = x.body
    if x.meta is not None:
        row.meta_json = json.dumps(x.meta)
    if x.date is not None:
        row.date = x.date

    q.commit()
    q.refresh(row)
    return _row_to_schema(row)
