import datetime as dt
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..services.symptom_report import compute_headache_summary

router = APIRouter()

@router.get("/acupuncture-sessions")
def get_acupuncture_sessions(db: Session = Depends(get_db)):
    activities = db.query(models.Activity).filter(models.Activity.name.ilike("%acupuncture%")).all()
    if not activities:
        return {"sessions": []}
    
    activity_ids = [a.id for a in activities]
    
    moods = (
        db.query(models.Mood)
        .join(models.mood_activities)
        .filter(models.mood_activities.c.activity_id.in_(activity_ids))
        .order_by(models.Mood.timestamp.desc())
        .all()
    )
    
    dates = sorted(list(set([m.timestamp.date() for m in moods])), reverse=True)
    return {"sessions": [d.isoformat() for d in dates]}

@router.get("/headache-summary")
def get_headache_summary(
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    db: Session = Depends(get_db),
):
    result = compute_headache_summary(db, start_date=start_date, end_date=end_date)
    # Maintain backwards compatibility for any consumers expecting 'triggers'
    result["triggers"] = result.get("triggers_day_before", [])
    return result
