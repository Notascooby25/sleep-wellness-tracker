from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from .. import models, schemas

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

    db_activities = db.query(models.Activity).filter(models.Activity.id.in_(entry.activity_ids)).all()
    if len(db_activities) != len(entry.activity_ids):
        raise HTTPException(status_code=400, detail='One or more activity_ids do not exist')

    db_entry = models.MoodEntry(
        mood_score=entry.mood_score,
        note=entry.note,
        timestamp=entry.timestamp,
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    # link activities
    for act_id in entry.activity_ids:
        link = models.MoodEntryActivity(entry_id=db_entry.id, activity_id=act_id)
        db.add(link)

    db.commit()

    return schemas.MoodEntry(
        id=db_entry.id,
        mood_score=db_entry.mood_score,
        note=db_entry.note,
        timestamp=db_entry.timestamp,
        created_at=db_entry.created_at,
        activity_ids=entry.activity_ids
    )

@router.get("", include_in_schema=False)
@router.get("/", response_model=List[schemas.MoodEntryResponse])
def list_mood_entries(db: Session = Depends(get_db)):
    entries = db.query(models.MoodEntry).all()
    return entries

@router.get("/{entry_id}", response_model=schemas.MoodEntryResponse)
def get_mood_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(models.MoodEntry).filter(models.MoodEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Mood entry not found")
    return entry
