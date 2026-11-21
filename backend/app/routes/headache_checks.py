"""The daily "Headache today?" check."""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..database import get_db
from ..services.insight_dates import UK_TZ
from ..services.item_roles import is_symptom
from ..services.weather_daily import record_location_if_today

router = APIRouter(prefix="/headache-checks", tags=["headache-checks"])

ONSETS = ("woke", "morning", "afternoon", "evening")
MAX_LIST_DAYS = 731


class HeadacheCheckIn(BaseModel):
    had_headache: bool
    onset: str | None = None
    # Where the phone was when answering; only used when answering for today.
    latitude: float | None = None
    longitude: float | None = None


def _serialize(check_date: dt.date, check: models.HeadacheCheck | None, logged: list[str]) -> dict:
    return {
        "date": check_date.isoformat(),
        "answered": check is not None,
        "had_headache": check.had_headache if check is not None else None,
        "onset": check.onset if check is not None else None,
        "logged_symptoms": logged,
    }


def _logged_symptoms(db: Session, day: dt.date) -> list[str]:
    start = dt.datetime.combine(day, dt.time(), tzinfo=UK_TZ)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), tzinfo=UK_TZ)
    moods = (
        db.query(models.Mood)
        .options(selectinload(models.Mood.activities).selectinload(models.Activity.category))
        .filter(models.Mood.timestamp >= start, models.Mood.timestamp < end)
        .all()
    )
    names = {(a.name or "").strip() for m in moods for a in m.activities if is_symptom(a)}
    return sorted(n for n in names if n)


@router.get("")
def list_headache_checks(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    if start_date > end_date or (end_date - start_date).days + 1 > MAX_LIST_DAYS:
        raise HTTPException(status_code=400, detail="Choose a start date on or before the end date, within 2 years.")
    rows = (
        db.query(models.HeadacheCheck)
        .filter(models.HeadacheCheck.check_date >= start_date, models.HeadacheCheck.check_date <= end_date)
        .order_by(models.HeadacheCheck.check_date.asc())
        .all()
    )
    return [_serialize(r.check_date, r, []) for r in rows]


@router.get("/{check_date}")
def get_headache_check(check_date: dt.date, db: Session = Depends(get_db)):
    check = db.query(models.HeadacheCheck).filter(models.HeadacheCheck.check_date == check_date).first()
    return _serialize(check_date, check, _logged_symptoms(db, check_date))


@router.put("/{check_date}")
def save_headache_check(check_date: dt.date, payload: HeadacheCheckIn, db: Session = Depends(get_db)):
    onset = payload.onset if payload.had_headache else None
    if onset is not None and onset not in ONSETS:
        raise HTTPException(status_code=400, detail=f"onset must be one of {', '.join(ONSETS)}")
    check = db.query(models.HeadacheCheck).filter(models.HeadacheCheck.check_date == check_date).first()
    if check is None:
        check = models.HeadacheCheck(check_date=check_date, had_headache=payload.had_headache, onset=onset)
        db.add(check)
    else:
        check.had_headache = payload.had_headache
        check.onset = onset
    db.commit()
    db.refresh(check)
    try:
        record_location_if_today(db, check_date, payload.latitude, payload.longitude)
    except Exception:
        db.rollback()
    return _serialize(check_date, check, _logged_symptoms(db, check_date))


@router.delete("/{check_date}")
def clear_headache_check(check_date: dt.date, db: Session = Depends(get_db)):
    db.query(models.HeadacheCheck).filter(models.HeadacheCheck.check_date == check_date).delete()
    db.commit()
    return _serialize(check_date, None, _logged_symptoms(db, check_date))
