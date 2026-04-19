from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/mood", tags=["mood"])

@router.get("", response_model=List[schemas.MoodRead])
def list_mood_entries(db: Session = Depends(get_db)):
    rows = db.query(models.Mood).all()
    result = []
    for r in rows:
        activity_ids = [a.id for a in r.activities]
        result.append({
            "id": r.id,
            "mood_score": r.mood_score,
            # API now returns `notes`, still reading DB column `note`
            "notes": r.notes,
            "timestamp": r.timestamp,
            "created_at": r.created_at,
            "activity_ids": activity_ids,
        })
    return result

@router.post("", response_model=schemas.MoodRead)
def create_mood_entry(payload: schemas.MoodCreate, db: Session = Depends(get_db)):
    # payload.notes is populated whether client sent "note" or "notes"
    db_mood = models.Mood(
        mood_score=payload.mood_score,
        notes=payload.notes,
        timestamp=payload.timestamp,
    )
    db.add(db_mood)
    db.commit()

    if payload.activity_ids:
        activities = db.query(models.Activity).filter(
            models.Activity.id.in_(payload.activity_ids)
        ).all()
        db_mood.activities = activities
        db.commit()

    db.refresh(db_mood)
    activity_ids = [a.id for a in db_mood.activities]

    return {
        "id": db_mood.id,
        "mood_score": db_mood.mood_score,
        "notes": db_mood.notes,
        "timestamp": db_mood.timestamp,
        "created_at": db_mood.created_at,
        "activity_ids": activity_ids,
    }

@router.get("/{entry_id}", response_model=schemas.MoodRead)
def get_mood_entry(entry_id: int, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    activity_ids = [a.id for a in m.activities]

    return {
        "id": m.id,
        "mood_score": m.mood_score,
        "notes": m.notes,
        "timestamp": m.timestamp,
        "created_at": m.created_at,
        "activity_ids": activity_ids,
    }


@router.put("/{entry_id}", response_model=schemas.MoodRead)
def update_mood_entry(entry_id: int, payload: schemas.MoodUpdate, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    m.mood_score = payload.mood_score
    m.notes = payload.notes
    m.timestamp = payload.timestamp

    activities = []
    if payload.activity_ids:
        activities = db.query(models.Activity).filter(
            models.Activity.id.in_(payload.activity_ids)
        ).all()
    m.activities = activities

    db.commit()
    db.refresh(m)

    activity_ids = [a.id for a in m.activities]
    return {
        "id": m.id,
        "mood_score": m.mood_score,
        "notes": m.notes,
        "timestamp": m.timestamp,
        "created_at": m.created_at,
        "activity_ids": activity_ids,
    }


@router.delete("/{entry_id}")
def delete_mood_entry(entry_id: int, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    db.delete(m)
    db.commit()
    return {"ok": True, "id": entry_id}
