from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from .. import models, schemas
from typing import List, Set
from sqlalchemy.exc import IntegrityError


router = APIRouter()


# -------------------------
# Categories
# -------------------------

@router.post("/categories", response_model=schemas.Category)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    db_cat = models.Category(name=category.name)
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return db_cat


@router.get("/categories", response_model=list[schemas.Category])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()


# -------------------------
# Activities
# -------------------------

@router.post("/activities", response_model=schemas.Activity)
def create_activity(activity: schemas.ActivityCreate, db: Session = Depends(get_db)):
    db_act = models.Activity(name=activity.name, category_id=activity.category_id)
    db.add(db_act)
    db.commit()
    db.refresh(db_act)
    return db_act


@router.get("/activities", response_model=list[schemas.Activity])
def list_activities(db: Session = Depends(get_db)):
    return db.query(models.Activity).all()


# -------------------------
# Mood Entries
# -------------------------

@router.post("/mood", response_model=schemas.MoodEntry)
def create_mood_entry(entry: schemas.MoodEntryCreate, db: Session = Depends(get_db)):
    # validate mood_score to match DB constraint (avoid DB check violation)
    if not (1 <= entry.mood_score <= 5):
        raise HTTPException(status_code=400, detail='mood_score must be between 1 and 5')

    # Ensure activity ids exist
    db_activities = db.query(models.Activity).filter(models.Activity.id.in_(entry.activity_ids)).all()
    if len(db_activities) != len(entry.activity_ids):
        raise HTTPException(status_code=400, detail='One or more activity_ids do not exist')

    # Normalize timestamp (assumes entry.timestamp is already a datetime or ISO string)
    ts = entry.timestamp
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid timestamp format")

    requested_activity_ids: Set[int] = set(entry.activity_ids or [])

    # 1) Look for existing candidate entries with same timestamp, mood_score and note
    candidates = (
        db.query(models.MoodEntry)
        .filter(
            models.MoodEntry.timestamp == ts,
            models.MoodEntry.mood_score == entry.mood_score,
            models.MoodEntry.note == entry.note,
        )
        .all()
    )

    # 2) Compare activity sets for each candidate; if identical, return it (idempotent)
    for cand in candidates:
        assoc_rows = (
            db.query(models.MoodEntryActivity)
            .filter(models.MoodEntryActivity.entry_id == cand.id)
            .all()
        )
        cand_activity_ids = {a.activity_id for a in assoc_rows}
        if cand_activity_ids == requested_activity_ids:
            return cand

    # 3) No identical entry found — attempt to create one
    new_entry = models.MoodEntry(
        mood_score=entry.mood_score,
        note=entry.note,
        timestamp=ts,
    )

    try:
        db.add(new_entry)
        db.flush()  # assign id without committing

        # create association rows
        for aid in requested_activity_ids:
            db.add(models.MoodEntryActivity(entry_id=new_entry.id, activity_id=aid))

        db.commit()
        db.refresh(new_entry)
        return new_entry

    except IntegrityError:
        # Unique index prevented duplicate insert (race or double-post).
        db.rollback()
        # Find and return the existing row deterministically
        existing = (
            db.query(models.MoodEntry)
            .filter(
                models.MoodEntry.timestamp == ts,
                models.MoodEntry.mood_score == entry.mood_score,
                models.MoodEntry.note == entry.note,
            )
            .first()
        )
        if existing:
            return existing
        raise HTTPException(status_code=500, detail="Could not create or find mood entry")

