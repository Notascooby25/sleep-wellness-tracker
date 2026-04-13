# backend/app/routers/mood.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import Mood, Activity
from ..schemas import MoodCreate, MoodRead

router = APIRouter(prefix="/mood", tags=["mood"])

@router.get("", response_model=List[MoodRead])
def get_moods(db: Session = Depends(get_db)):
    rows = db.query(Mood).all()
    result = []
    for r in rows:
        activity_ids = [a.id for a in r.activities]
        result.append({
            "id": r.id,
            "mood_score": r.mood_score,
            "note": r.note,
            "timestamp": r.timestamp,
            "created_at": r.created_at,
            "activity_ids": activity_ids
        })
    return result

@router.post("", response_model=MoodRead)
def create_mood(mood: MoodCreate, db: Session = Depends(get_db)):
    db_mood = Mood(
        mood_score=mood.mood_score,
        note=mood.note,
        timestamp=mood.timestamp
    )
    db.add(db_mood)
    db.commit()
    # Attach activities if provided
    if mood.activity_ids:
        activities = db.query(Activity).filter(Activity.id.in_(mood.activity_ids)).all()
        db_mood.activities = activities
        db.commit()
        db.refresh(db_mood)
    activity_ids = [a.id for a in db_mood.activities]
    return {
        "id": db_mood.id,
        "mood_score": db_mood.mood_score,
        "note": db_mood.note,
        "timestamp": db_mood.timestamp,
        "created_at": db_mood.created_at,
        "activity_ids": activity_ids
    }

@router.get("/{entry_id}", response_model=MoodRead)
def get_mood(entry_id: int, db: Session = Depends(get_db)):
    m = db.query(Mood).filter(Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    activity_ids = [a.id for a in m.activities]
    return {
        "id": m.id,
        "mood_score": m.mood_score,
        "note": m.note,
        "timestamp": m.timestamp,
        "created_at": m.created_at,
        "activity_ids": activity_ids
    }
