import datetime as dt
import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..services.garmin_sync import (
    sync_body_battery_if_due,
    sync_hrv_if_due,
    sync_hydration_if_due,
    sync_resting_heart_rate_if_due,
    sync_sleep_if_due,
    sync_smart,
    sync_stress_if_due,
)
from ..garmin_client import GarminRateLimitError

logger = logging.getLogger("app.garmin")

router = APIRouter(prefix="/garmin", tags=["garmin"])


def _serialize_sleep(row: models.GarminSleepDaily) -> dict:
    return {
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


def _serialize_body_battery(row: models.GarminBodyBatteryDaily) -> dict:
    return {
        "date": row.battery_date.isoformat(),
        "morning_value": row.morning_value,
        "end_of_day_value": row.end_of_day_value,
        "peak_value": row.peak_value,
        "low_value": row.low_value,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_hrv(row: models.GarminHRVDaily) -> dict:
    return {
        "date": row.hrv_date.isoformat(),
        "weekly_avg": row.weekly_avg,
        "baseline_low": row.baseline_low,
        "baseline_high": row.baseline_high,
        "status": row.status,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_rhr(row: models.GarminRestingHeartRateDaily) -> dict:
    return {
        "date": row.heart_rate_date.isoformat(),
        "resting_heart_rate": row.resting_heart_rate,
        "min_heart_rate": row.min_heart_rate,
        "max_heart_rate": row.max_heart_rate,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_stress(row: models.GarminStressDaily) -> dict:
    return {
        "date": row.stress_date.isoformat(),
        "overall_stress_level": row.overall_stress_level,
        "rest_stress_duration": row.rest_stress_duration,
        "low_stress_duration": row.low_stress_duration,
        "medium_stress_duration": row.medium_stress_duration,
        "high_stress_duration": row.high_stress_duration,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_hydration(row: models.GarminHydrationDaily) -> dict:
    return {
        "date": row.hydration_date.isoformat(),
        "consumed_ml": row.consumed_ml,
        "goal_ml": row.goal_ml,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/sync-now")
def sync_now(
    mode: str = Query(default="smart", pattern="^(smart|sleep|body|hrv|rhr|stress|hydration|all)$"),
    force: bool = Query(default=False),
    backfill_days: int | None = Query(default=None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    logger.info("/garmin/sync-now called; mode=%s force=%s backfill_days=%s", mode, force, backfill_days)
    try:
        if mode == "sleep":
            return {"sleep": sync_sleep_if_due(db, force=force, backfill_days=backfill_days)}
        if mode == "body":
            return {"body_battery": sync_body_battery_if_due(db, force=force, backfill_days=backfill_days)}
        if mode == "hrv":
            return {"hrv": sync_hrv_if_due(db, force=force, backfill_days=backfill_days)}
        if mode == "rhr":
            return {"resting_heart_rate": sync_resting_heart_rate_if_due(db, force=force, backfill_days=backfill_days)}
        if mode == "stress":
            return {"stress": sync_stress_if_due(db, force=force, backfill_days=backfill_days)}
        if mode == "hydration":
            return {"hydration": sync_hydration_if_due(db, force=force, backfill_days=backfill_days)}
        if mode == "all":
            return {
                "sleep": sync_sleep_if_due(db, force=True, backfill_days=backfill_days),
                "body_battery": sync_body_battery_if_due(db, force=True, backfill_days=backfill_days),
                "hrv": sync_hrv_if_due(db, force=True, backfill_days=backfill_days),
                "resting_heart_rate": sync_resting_heart_rate_if_due(db, force=True, backfill_days=backfill_days),
                "stress": sync_stress_if_due(db, force=True, backfill_days=backfill_days),
                "hydration": sync_hydration_if_due(db, force=True, backfill_days=backfill_days),
            }
        return sync_smart(db, force=force, backfill_days=backfill_days)
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
    return {"data": _serialize_sleep(row)}


@router.get("/sleep/by-date")
def get_sleep_by_date(date: dt.date = Query(...), db: Session = Depends(get_db)):
    logger.info("/garmin/sleep/by-date called; date=%s", date.isoformat())
    row = db.query(models.GarminSleepDaily).filter(models.GarminSleepDaily.sleep_date == date).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_sleep(row)}


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
    return {"data": [_serialize_sleep(row) for row in rows]}


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
    return {"data": _serialize_body_battery(row)}


@router.get("/body-battery/by-date")
def get_body_battery_by_date(date: dt.date = Query(...), db: Session = Depends(get_db)):
    logger.info("/garmin/body-battery/by-date called; date=%s", date.isoformat())
    row = db.query(models.GarminBodyBatteryDaily).filter(models.GarminBodyBatteryDaily.battery_date == date).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_body_battery(row)}


@router.get("/body-battery/range")
def get_body_battery_range(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    logger.info("/garmin/body-battery/range called; start_date=%s end_date=%s", start_date.isoformat(), end_date.isoformat())
    rows = (
        db.query(models.GarminBodyBatteryDaily)
        .filter(models.GarminBodyBatteryDaily.battery_date >= start_date)
        .filter(models.GarminBodyBatteryDaily.battery_date <= end_date)
        .order_by(models.GarminBodyBatteryDaily.battery_date.desc())
        .all()
    )
    return {"data": [_serialize_body_battery(row) for row in rows]}


@router.get("/hrv/latest")
def get_latest_hrv(db: Session = Depends(get_db)):
    logger.info("/garmin/hrv/latest called")
    row = db.query(models.GarminHRVDaily).order_by(models.GarminHRVDaily.hrv_date.desc()).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_hrv(row)}


@router.get("/hrv/by-date")
def get_hrv_by_date(date: dt.date = Query(...), db: Session = Depends(get_db)):
    logger.info("/garmin/hrv/by-date called; date=%s", date.isoformat())
    row = db.query(models.GarminHRVDaily).filter(models.GarminHRVDaily.hrv_date == date).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_hrv(row)}


@router.get("/hrv/range")
def get_hrv_range(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    logger.info("/garmin/hrv/range called; start_date=%s end_date=%s", start_date.isoformat(), end_date.isoformat())
    rows = (
        db.query(models.GarminHRVDaily)
        .filter(models.GarminHRVDaily.hrv_date >= start_date)
        .filter(models.GarminHRVDaily.hrv_date <= end_date)
        .order_by(models.GarminHRVDaily.hrv_date.desc())
        .all()
    )
    return {"data": [_serialize_hrv(row) for row in rows]}


@router.get("/resting-heart-rate/latest")
def get_latest_resting_heart_rate(db: Session = Depends(get_db)):
    logger.info("/garmin/resting-heart-rate/latest called")
    row = (
        db.query(models.GarminRestingHeartRateDaily)
        .order_by(models.GarminRestingHeartRateDaily.heart_rate_date.desc())
        .first()
    )
    if not row:
        return {"data": None}
    return {"data": _serialize_rhr(row)}


@router.get("/resting-heart-rate/by-date")
def get_resting_heart_rate_by_date(date: dt.date = Query(...), db: Session = Depends(get_db)):
    logger.info("/garmin/resting-heart-rate/by-date called; date=%s", date.isoformat())
    row = (
        db.query(models.GarminRestingHeartRateDaily)
        .filter(models.GarminRestingHeartRateDaily.heart_rate_date == date)
        .first()
    )
    if not row:
        return {"data": None}
    return {"data": _serialize_rhr(row)}


@router.get("/resting-heart-rate/range")
def get_resting_heart_rate_range(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    logger.info(
        "/garmin/resting-heart-rate/range called; start_date=%s end_date=%s",
        start_date.isoformat(),
        end_date.isoformat(),
    )
    rows = (
        db.query(models.GarminRestingHeartRateDaily)
        .filter(models.GarminRestingHeartRateDaily.heart_rate_date >= start_date)
        .filter(models.GarminRestingHeartRateDaily.heart_rate_date <= end_date)
        .order_by(models.GarminRestingHeartRateDaily.heart_rate_date.desc())
        .all()
    )
    return {"data": [_serialize_rhr(row) for row in rows]}


@router.get("/stress/latest")
def get_latest_stress(db: Session = Depends(get_db)):
    logger.info("/garmin/stress/latest called")
    row = db.query(models.GarminStressDaily).order_by(models.GarminStressDaily.stress_date.desc()).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_stress(row)}


@router.get("/stress/by-date")
def get_stress_by_date(date: dt.date = Query(...), db: Session = Depends(get_db)):
    logger.info("/garmin/stress/by-date called; date=%s", date.isoformat())
    row = db.query(models.GarminStressDaily).filter(models.GarminStressDaily.stress_date == date).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_stress(row)}


@router.get("/stress/range")
def get_stress_range(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    logger.info("/garmin/stress/range called; start_date=%s end_date=%s", start_date.isoformat(), end_date.isoformat())
    rows = (
        db.query(models.GarminStressDaily)
        .filter(models.GarminStressDaily.stress_date >= start_date)
        .filter(models.GarminStressDaily.stress_date <= end_date)
        .order_by(models.GarminStressDaily.stress_date.desc())
        .all()
    )
    return {"data": [_serialize_stress(row) for row in rows]}


@router.get("/hydration/latest")
def get_latest_hydration(db: Session = Depends(get_db)):
    logger.info("/garmin/hydration/latest called")
    row = db.query(models.GarminHydrationDaily).order_by(models.GarminHydrationDaily.hydration_date.desc()).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_hydration(row)}


@router.get("/hydration/by-date")
def get_hydration_by_date(date: dt.date = Query(...), db: Session = Depends(get_db)):
    logger.info("/garmin/hydration/by-date called; date=%s", date.isoformat())
    row = db.query(models.GarminHydrationDaily).filter(models.GarminHydrationDaily.hydration_date == date).first()
    if not row:
        return {"data": None}
    return {"data": _serialize_hydration(row)}


@router.get("/hydration/range")
def get_hydration_range(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    logger.info("/garmin/hydration/range called; start_date=%s end_date=%s", start_date.isoformat(), end_date.isoformat())
    rows = (
        db.query(models.GarminHydrationDaily)
        .filter(models.GarminHydrationDaily.hydration_date >= start_date)
        .filter(models.GarminHydrationDaily.hydration_date <= end_date)
        .order_by(models.GarminHydrationDaily.hydration_date.desc())
        .all()
    )
    return {"data": [_serialize_hydration(row) for row in rows]}
