import datetime as dt
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..garmin_client import GarminClientError, GarminRateLimitError, get_garmin_client, is_garmin_configured
from .. import models

logger = logging.getLogger("app.garmin")

SLEEP_SYNC_KEY = "sleep_daily"
BODY_SYNC_KEY = "body_battery_daily"
HRV_SYNC_KEY = "hrv_daily"
RHR_SYNC_KEY = "resting_heart_rate_daily"
STRESS_SYNC_KEY = "stress_daily"
HYDRATION_SYNC_KEY = "hydration_daily"
MIN_SYNC_INTERVAL_MINUTES = 45
UK_TZ = ZoneInfo("Europe/London")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except Exception:
        logger.warning("Invalid integer for %s=%r; using default=%s", name, raw, default)
        return default


SLEEP_BACKFILL_DAYS = _env_int("GARMIN_SLEEP_BACKFILL_DAYS", 7)
BODY_BACKFILL_DAYS = _env_int("GARMIN_BODY_BACKFILL_DAYS", 7)
HRV_BACKFILL_DAYS = _env_int("GARMIN_HRV_BACKFILL_DAYS", 7)
RHR_BACKFILL_DAYS = _env_int("GARMIN_RHR_BACKFILL_DAYS", 7)
STRESS_BACKFILL_DAYS = _env_int("GARMIN_STRESS_BACKFILL_DAYS", 7)
HYDRATION_BACKFILL_DAYS = _env_int("GARMIN_HYDRATION_BACKFILL_DAYS", 7)


def _uk_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone(UK_TZ)


def _today() -> dt.date:
    return _uk_now().date()


def _recent_dates(days: int, end_date: Optional[dt.date] = None) -> List[dt.date]:
    if days < 1:
        return []

    target_end = end_date or _today()
    start_date = target_end - dt.timedelta(days=days - 1)
    return [start_date + dt.timedelta(days=offset) for offset in range(days)]


def _get_sync_state(db: Session, key: str) -> models.GarminSyncState:
    state = db.query(models.GarminSyncState).filter(models.GarminSyncState.key == key).first()
    if state:
        return state
    state = models.GarminSyncState(key=key)
    db.add(state)
    db.commit()
    db.refresh(state)
    logger.info("Created Garmin sync state row; key=%s", key)
    return state


def _recently_synced(last_synced_at: Optional[dt.datetime]) -> bool:
    if not last_synced_at:
        return False
    delta = dt.datetime.now(dt.timezone.utc) - last_synced_at.astimezone(dt.timezone.utc)
    return delta.total_seconds() < (MIN_SYNC_INTERVAL_MINUTES * 60)


def _recovery_window_open(now_local: dt.datetime) -> bool:
    return now_local.time() >= dt.time(hour=8, minute=0)


def _day_close_window_open(now_local: dt.datetime) -> bool:
    return now_local.time() >= dt.time(hour=23, minute=50)


def _get_nested_value(src: Dict[str, Any], key_path: str) -> Any:
    node: Any = src
    for part in key_path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
        if node is None:
            return None
    return node


def _get_value(d: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = _get_nested_value(d, key) if "." in key else d.get(key)
        if value is not None:
            return value
    return None


def _get_int(d: Dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = _get_value(d, key)
        if value is None:
            continue
        try:
            return int(float(value))
        except Exception:
            continue
    return None


def _get_text(d: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = _get_value(d, key)
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        else:
            return str(value)
    return None


def _to_datetime(ms_epoch: Optional[int]) -> Optional[dt.datetime]:
    if not ms_epoch:
        return None
    try:
        return dt.datetime.fromtimestamp(int(ms_epoch) / 1000, tz=dt.timezone.utc)
    except Exception:
        return None


def _call_client_method(client: Any, candidates: List[str], date_str: str) -> Dict[str, Any]:
    for method_name in candidates:
        method = getattr(client, method_name, None)
        if callable(method):
            payload = method(date_str)
            return payload if isinstance(payload, dict) else (payload or {})
    raise GarminClientError(f"Garmin client does not support any of: {', '.join(candidates)}")


def _upsert_sleep_daily(db: Session, sleep_date: dt.date, payload: Dict[str, Any]) -> models.GarminSleepDaily:
    row = db.query(models.GarminSleepDaily).filter(models.GarminSleepDaily.sleep_date == sleep_date).first()
    if not row:
        row = models.GarminSleepDaily(sleep_date=sleep_date)
        db.add(row)

    dto = payload.get("dailySleepDTO") or payload

    row.sleep_start = _to_datetime(_get_int(dto, "sleepStartTimestampGMT", "sleepStartTimestampLocal"))
    row.sleep_end = _to_datetime(_get_int(dto, "sleepEndTimestampGMT", "sleepEndTimestampLocal"))

    raw_total = _get_int(dto, "sleepTimeSeconds", "totalSleepSeconds")
    row.total_sleep_minutes = raw_total // 60 if raw_total is not None else None
    raw_deep = _get_int(dto, "deepSleepSeconds")
    row.deep_sleep_minutes = raw_deep // 60 if raw_deep is not None else None
    raw_light = _get_int(dto, "lightSleepSeconds")
    row.light_sleep_minutes = raw_light // 60 if raw_light is not None else None
    raw_rem = _get_int(dto, "remSleepSeconds")
    row.rem_sleep_minutes = raw_rem // 60 if raw_rem is not None else None
    raw_awake = _get_int(dto, "awakeSleepSeconds")
    row.awake_minutes = raw_awake // 60 if raw_awake is not None else None

    sleep_scores = dto.get("sleepScores") or {}
    overall = sleep_scores.get("overall")
    if isinstance(overall, dict):
        row.sleep_score = _get_int(overall, "value")
    else:
        score = _get_int(dto, "overallSleepScore")
        row.sleep_score = score if score is not None else (_get_int({"v": overall}, "v") if overall is not None else None)

    row.body_battery_wakeup = _get_int(dto, "bodyBatteryWakeup")
    row.body_battery_bedtime = _get_int(dto, "bodyBatteryBedtime")
    row.payload = payload

    db.commit()
    db.refresh(row)
    logger.info(
        "Upserted Garmin sleep row; date=%s total_sleep_minutes=%s sleep_score=%s dto_keys=%s",
        sleep_date.isoformat(),
        row.total_sleep_minutes,
        row.sleep_score,
        sorted(dto.keys()),
    )
    return row


def _upsert_body_daily(db: Session, battery_date: dt.date, payload: Dict[str, Any]) -> models.GarminBodyBatteryDaily:
    row = db.query(models.GarminBodyBatteryDaily).filter(models.GarminBodyBatteryDaily.battery_date == battery_date).first()
    if not row:
        row = models.GarminBodyBatteryDaily(battery_date=battery_date)
        db.add(row)

    row.morning_value = _get_int(payload, "morningValue", "bodyBatteryMorning", "bodyBatteryLowestValue")
    row.end_of_day_value = _get_int(payload, "endOfDayValue", "bodyBatteryEvening", "bodyBatteryMostRecentValue")
    row.peak_value = _get_int(payload, "peakValue", "maxValue", "bodyBatteryHighestValue")
    row.low_value = _get_int(payload, "lowValue", "minValue", "bodyBatteryLowestValue")
    row.payload = payload

    db.commit()
    db.refresh(row)
    logger.info(
        "Upserted Garmin body battery row; date=%s morning=%s end_of_day=%s payload_keys=%s",
        battery_date.isoformat(),
        row.morning_value,
        row.end_of_day_value,
        sorted(payload.keys()),
    )
    return row


def _upsert_hrv_daily(db: Session, hrv_date: dt.date, payload: Dict[str, Any]) -> models.GarminHRVDaily:
    row = db.query(models.GarminHRVDaily).filter(models.GarminHRVDaily.hrv_date == hrv_date).first()
    if not row:
        row = models.GarminHRVDaily(hrv_date=hrv_date)
        db.add(row)

    dto = payload.get("hrvSummary") or payload.get("hrvStatus") or payload
    row.weekly_avg = _get_int(dto, "weeklyAvg", "weeklyAverage", "lastNightAvg", "lastNightAverage", "value")
    row.baseline_low = _get_int(dto, "baseline.low", "baselineLower", "baseline.lower")
    row.baseline_high = _get_int(dto, "baseline.high", "baselineUpper", "baseline.upper")
    row.status = _get_text(dto, "status", "status.value", "hrvStatus")
    row.payload = payload

    db.commit()
    db.refresh(row)
    logger.info(
        "Upserted Garmin HRV row; date=%s weekly_avg=%s status=%s payload_keys=%s",
        hrv_date.isoformat(),
        row.weekly_avg,
        row.status,
        sorted(dto.keys()) if isinstance(dto, dict) else [],
    )
    return row


def _upsert_rhr_daily(db: Session, heart_rate_date: dt.date, payload: Dict[str, Any]) -> models.GarminRestingHeartRateDaily:
    row = (
        db.query(models.GarminRestingHeartRateDaily)
        .filter(models.GarminRestingHeartRateDaily.heart_rate_date == heart_rate_date)
        .first()
    )
    if not row:
        row = models.GarminRestingHeartRateDaily(heart_rate_date=heart_rate_date)
        db.add(row)

    row.resting_heart_rate = _get_int(payload, "restingHeartRate", "heartRateValues.restingHeartRate")
    row.min_heart_rate = _get_int(payload, "minHeartRate", "heartRateValues.minHeartRate")
    row.max_heart_rate = _get_int(payload, "maxHeartRate", "heartRateValues.maxHeartRate")
    row.payload = payload

    db.commit()
    db.refresh(row)
    logger.info(
        "Upserted Garmin resting heart rate row; date=%s resting=%s payload_keys=%s",
        heart_rate_date.isoformat(),
        row.resting_heart_rate,
        sorted(payload.keys()),
    )
    return row


def _upsert_stress_daily(db: Session, stress_date: dt.date, payload: Dict[str, Any]) -> models.GarminStressDaily:
    row = db.query(models.GarminStressDaily).filter(models.GarminStressDaily.stress_date == stress_date).first()
    if not row:
        row = models.GarminStressDaily(stress_date=stress_date)
        db.add(row)

    row.overall_stress_level = _get_int(payload, "overallStressLevel", "averageStressLevel", "stressLevel")
    row.rest_stress_duration = _get_int(payload, "restStressDuration", "restDuration")
    row.low_stress_duration = _get_int(payload, "lowStressDuration", "lowDuration")
    row.medium_stress_duration = _get_int(payload, "mediumStressDuration", "mediumDuration")
    row.high_stress_duration = _get_int(payload, "highStressDuration", "highDuration")
    row.payload = payload

    db.commit()
    db.refresh(row)
    logger.info(
        "Upserted Garmin stress row; date=%s overall=%s payload_keys=%s",
        stress_date.isoformat(),
        row.overall_stress_level,
        sorted(payload.keys()),
    )
    return row


def _upsert_hydration_daily(db: Session, hydration_date: dt.date, payload: Dict[str, Any]) -> models.GarminHydrationDaily:
    row = db.query(models.GarminHydrationDaily).filter(models.GarminHydrationDaily.hydration_date == hydration_date).first()
    if not row:
        row = models.GarminHydrationDaily(hydration_date=hydration_date)
        db.add(row)

    row.consumed_ml = _get_int(payload, "consumedMilliliters", "consumedML", "totalWaterIntake", "valueInML")
    row.goal_ml = _get_int(payload, "goalMilliliters", "goalML", "dailyGoalInML", "goalInML")
    row.payload = payload

    db.commit()
    db.refresh(row)
    logger.info(
        "Upserted Garmin hydration row; date=%s consumed_ml=%s goal_ml=%s payload_keys=%s",
        hydration_date.isoformat(),
        row.consumed_ml,
        row.goal_ml,
        sorted(payload.keys()),
    )
    return row


def _fetch_sleep_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_sleep_data"], date_str)


def _fetch_body_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_stats"], date_str)


def _fetch_hrv_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_hrv_data", "get_hrv", "get_hrv_stats"], date_str)


def _fetch_rhr_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_heart_rates", "get_heart_rate", "get_heart_rate_data"], date_str)


def _fetch_stress_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_stress_data", "get_stress", "get_stress_stats"], date_str)


def _fetch_hydration_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_hydration_data", "get_hydration", "get_hydration_stats"], date_str)


def _sync_metric_dates(
    client: Any,
    db: Session,
    dates: List[dt.date],
    metric_name: str,
    fetch_payload: Callable[[Any, str], Dict[str, Any]],
    upsert_row: Callable[[Session, dt.date, Dict[str, Any]], Any],
) -> Tuple[List[str], List[Dict[str, str]]]:
    synced_dates: List[str] = []
    failed_dates: List[Dict[str, str]] = []

    for target_date in dates:
        date_str = target_date.isoformat()
        try:
            logger.info("Requesting Garmin %s data; date=%s", metric_name, date_str)
            payload = fetch_payload(client, date_str) or {}
            logger.info(
                "Received Garmin %s payload; date=%s payload_keys=%s",
                metric_name,
                date_str,
                sorted(payload.keys()) if isinstance(payload, dict) else [],
            )
            upsert_row(db, target_date, payload)
            synced_dates.append(date_str)
        except Exception as exc:
            logger.exception("Failed syncing Garmin %s data; date=%s", metric_name, date_str)
            failed_dates.append({"date": date_str, "error": str(exc)})

    return synced_dates, failed_dates


def _sync_sleep_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "sleep", _fetch_sleep_payload, _upsert_sleep_daily)


def _sync_body_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "body battery", _fetch_body_payload, _upsert_body_daily)


def _sync_hrv_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "HRV", _fetch_hrv_payload, _upsert_hrv_daily)


def _sync_rhr_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "resting heart rate", _fetch_rhr_payload, _upsert_rhr_daily)


def _sync_stress_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "stress", _fetch_stress_payload, _upsert_stress_daily)


def _sync_hydration_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "hydration", _fetch_hydration_payload, _upsert_hydration_daily)


def _run_metric_sync(
    db: Session,
    *,
    force: bool,
    state_key: str,
    metric_name: str,
    backfill_days: int,
    sync_dates_fn: Callable[[Any, Session, List[dt.date]], Tuple[List[str], List[Dict[str, str]]]],
    latest_field: str,
    window_open: Callable[[dt.datetime], bool],
    skipped_reason: str,
) -> Dict[str, Any]:
    now_local = _uk_now()
    state = _get_sync_state(db, state_key)

    logger.info(
        "%s sync requested; force=%s now_local=%s last_synced_at=%s",
        metric_name,
        force,
        now_local.isoformat(),
        state.last_synced_at.isoformat() if state.last_synced_at else None,
    )

    if not is_garmin_configured():
        logger.warning("%s sync skipped: garmin_not_configured", metric_name)
        return {"status": "skipped", "reason": "garmin_not_configured"}
    if not force and _recently_synced(state.last_synced_at):
        logger.info("%s sync skipped: throttled_recent_sync", metric_name)
        return {"status": "skipped", "reason": "throttled_recent_sync"}
    if not force and not window_open(now_local):
        logger.info("%s sync skipped: %s", metric_name, skipped_reason)
        return {"status": "skipped", "reason": skipped_reason}
    if not force and state.last_synced_at and state.last_synced_at.date() >= _today():
        logger.info("%s sync skipped: already_synced_today", metric_name)
        return {"status": "skipped", "reason": "already_synced_today"}

    try:
        client = get_garmin_client()
        target_dates = _recent_dates(backfill_days)
        logger.info(
            "Running Garmin %s backfill; days=%s start_date=%s end_date=%s",
            metric_name,
            backfill_days,
            target_dates[0].isoformat(),
            target_dates[-1].isoformat(),
        )
        synced_dates, failed_dates = sync_dates_fn(client, db, target_dates)
    except GarminRateLimitError:
        raise
    except GarminClientError as exc:
        logger.error("%s sync failed with Garmin client error: %s", metric_name, exc)
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected %s sync failure", metric_name)
        return {"status": "error", "reason": f"{state_key}_sync_failed: {exc}"}

    if not synced_dates:
        logger.error("%s sync failed for all requested dates", metric_name)
        return {
            "status": "error",
            "reason": f"{state_key}_backfill_failed",
            "failed_dates": failed_dates,
        }

    state.last_synced_at = dt.datetime.now(dt.timezone.utc)
    state.detail = f"{state_key}_partial" if failed_dates else f"{state_key}_ok"
    db.commit()

    logger.info("%s sync complete; synced_dates=%s failed_count=%s", metric_name, synced_dates, len(failed_dates))

    return {
        "status": "partial" if failed_dates else "ok",
        latest_field: synced_dates[-1],
        "synced_dates": synced_dates,
        "failed_dates": failed_dates,
        "backfill_days": backfill_days,
    }


def sync_sleep_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=SLEEP_SYNC_KEY,
        metric_name="sleep",
        backfill_days=SLEEP_BACKFILL_DAYS,
        sync_dates_fn=_sync_sleep_dates,
        latest_field="sleep_date",
        window_open=_recovery_window_open,
        skipped_reason="outside_sleep_sync_window",
    )


def sync_body_battery_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=BODY_SYNC_KEY,
        metric_name="body battery",
        backfill_days=BODY_BACKFILL_DAYS,
        sync_dates_fn=_sync_body_dates,
        latest_field="battery_date",
        window_open=_day_close_window_open,
        skipped_reason="outside_body_sync_window",
    )


def sync_hrv_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=HRV_SYNC_KEY,
        metric_name="hrv",
        backfill_days=HRV_BACKFILL_DAYS,
        sync_dates_fn=_sync_hrv_dates,
        latest_field="hrv_date",
        window_open=_recovery_window_open,
        skipped_reason="outside_hrv_sync_window",
    )


def sync_resting_heart_rate_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=RHR_SYNC_KEY,
        metric_name="resting heart rate",
        backfill_days=RHR_BACKFILL_DAYS,
        sync_dates_fn=_sync_rhr_dates,
        latest_field="heart_rate_date",
        window_open=_recovery_window_open,
        skipped_reason="outside_rhr_sync_window",
    )


def sync_stress_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=STRESS_SYNC_KEY,
        metric_name="stress",
        backfill_days=STRESS_BACKFILL_DAYS,
        sync_dates_fn=_sync_stress_dates,
        latest_field="stress_date",
        window_open=_day_close_window_open,
        skipped_reason="outside_stress_sync_window",
    )


def sync_hydration_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=HYDRATION_SYNC_KEY,
        metric_name="hydration",
        backfill_days=HYDRATION_BACKFILL_DAYS,
        sync_dates_fn=_sync_hydration_dates,
        latest_field="hydration_date",
        window_open=_day_close_window_open,
        skipped_reason="outside_hydration_sync_window",
    )


def sync_smart(db: Session, force: bool = False) -> Dict[str, Any]:
    logger.info("Smart Garmin sync requested; force=%s", force)
    results = {
        "sleep": sync_sleep_if_due(db, force=force),
        "body_battery": sync_body_battery_if_due(db, force=force),
        "hrv": sync_hrv_if_due(db, force=force),
        "resting_heart_rate": sync_resting_heart_rate_if_due(db, force=force),
        "stress": sync_stress_if_due(db, force=force),
        "hydration": sync_hydration_if_due(db, force=force),
    }
    logger.info("Smart Garmin sync finished; results=%s", results)
    return results
