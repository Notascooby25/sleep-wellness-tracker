import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.symptom_report import (
    compute_appointment_summary,
    compute_headache_summary,
    compute_headache_triggers,
    get_acupuncture_session_dates,
)

router = APIRouter()


@router.get("/acupuncture-sessions")
def get_acupuncture_sessions(db: Session = Depends(get_db)):
    dates = get_acupuncture_session_dates(db)
    return {"sessions": [d.isoformat() for d in dates]}


@router.get("/headache-appointment-summary")
def get_headache_appointment_summary(
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return compute_appointment_summary(db, start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/headache-triggers")
def get_headache_triggers(
    window: str = Query("90d"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return compute_headache_triggers(db, window=window, start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/headache-summary")
def get_headache_summary(
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        result = compute_headache_summary(db, start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Maintain backwards compatibility for any consumers expecting 'triggers'
    result["triggers"] = result.get("triggers_day_before", [])
    return result
