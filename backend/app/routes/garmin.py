import datetime as dt
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..services.garmin_sync import sync_smart, sync_sleep_if_due, sync_body_battery_if_due
from ..garmin_client import GarminRateLimitError

logger = logging.getLogger("app.garmin")

router = APIRouter(prefix="/garmin", tags=["garmin"])


@router.post("/sync-now")
def sync_now(
    mode: str = Query(default="smart", pattern="^(smart|sleep|body|all)$"),
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    logger.info("/garmin/sync-now called; mode=%s force=%s", mode, force)
    try:
        if mode == "sleep":
            return {"sleep": sync_sleep_if_due(db, force=force)}
        if mode == "body":
            return {"body_battery": sync_body_battery_if_due(db, force=force)}
        if mode == "all":
            return {
                "sleep": sync_sleep_if_due(db, force=True),
                "body_battery": sync_body_battery_if_due(db, force=True),
            }
        return sync_smart(db, force=force)
    except GarminRateLimitError as exc:
        logger.warning("Garmin rate limit hit during sync: %s", exc)
        raise HTTPException(status_code=429, detail=str(exc))


@router.get("/sleep/latest")
def get_latest_sleep(db: Session = Depends(get_db)):
    logger.info("/garmin/sleep/latest called")
    row = (
        db.query(models.GarminSleepDaily)
        .order_by(models.GarminSleepDaily.sleep_date.desc())
        .first()
    )
    if not row:
        return {"data": None}
    return {
        "data": {
            "date": row.sleep_date.isoformat(),
            "sleep_start": row.sleep_start.isoformat() if row.sleep_start else None,
            "sleep_end": row.sleep_end.isoformat() if row.sleep_end else None,
            "total_sleep_minutes": row.total_sleep_minutes,
            "deep_sleep_minutes": row.deep_sleep_minutes,
            "light_sleep_minutes": row.light_sleep_minutes,
            "rem_sleep_minutes": row.rem_sleep_minutes,
            "awake_minutes": row.awake_minutes,
            "sleep_score": row.sleep_score,
            "body_battery_wakeup": row.body_battery_wakeup,
            "body_battery_bedtime": row.body_battery_bedtime,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    }


@router.get("/sleep/by-date")
def get_sleep_by_date(date: dt.date = Query(...), db: Session = Depends(get_db)):
    logger.info("/garmin/sleep/by-date called; date=%s", date.isoformat())
    row = db.query(models.GarminSleepDaily).filter(models.GarminSleepDaily.sleep_date == date).first()
    if not row:
        return {"data": None}
    return {
        "data": {
            "date": row.sleep_date.isoformat(),
            "total_sleep_minutes": row.total_sleep_minutes,
            "deep_sleep_minutes": row.deep_sleep_minutes,
            "light_sleep_minutes": row.light_sleep_minutes,
            "rem_sleep_minutes": row.rem_sleep_minutes,
            "awake_minutes": row.awake_minutes,
            "sleep_score": row.sleep_score,
            "body_battery_wakeup": row.body_battery_wakeup,
            "body_battery_bedtime": row.body_battery_bedtime,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    }


@router.get("/sleep/range")
def get_sleep_range(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    logger.info("/garmin/sleep/range called; start_date=%s end_date=%s", start_date.isoformat(), end_date.isoformat())
    rows = (
        db.query(models.GarminSleepDaily)
        .filter(models.GarminSleepDaily.sleep_date >= start_date)
        .filter(models.GarminSleepDaily.sleep_date <= end_date)
        .order_by(models.GarminSleepDaily.sleep_date.desc())
        .all()
    )

    return {
        "data": [
            {
                "date": row.sleep_date.isoformat(),
                "total_sleep_minutes": row.total_sleep_minutes,
                "deep_sleep_minutes": row.deep_sleep_minutes,
                "light_sleep_minutes": row.light_sleep_minutes,
                "rem_sleep_minutes": row.rem_sleep_minutes,
                "awake_minutes": row.awake_minutes,
                "sleep_score": row.sleep_score,
                "body_battery_wakeup": row.body_battery_wakeup,
                "body_battery_bedtime": row.body_battery_bedtime,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]
    }


@router.get("/body-battery/latest")
def get_latest_body_battery(db: Session = Depends(get_db)):
    logger.info("/garmin/body-battery/latest called")
    row = (
        db.query(models.GarminBodyBatteryDaily)
        .order_by(models.GarminBodyBatteryDaily.battery_date.desc())
        .first()
    )
    if not row:
        return {"data": None}
    return {
        "data": {
            "date": row.battery_date.isoformat(),
            "morning_value": row.morning_value,
            "end_of_day_value": row.end_of_day_value,
            "peak_value": row.peak_value,
            "low_value": row.low_value,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    }
