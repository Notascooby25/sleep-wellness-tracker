import datetime as dt
import logging
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..garmin_client import GarminClientError, GarminRateLimitError, get_garmin_client, is_garmin_configured
from .. import models

logger = logging.getLogger("app.garmin")

SLEEP_SYNC_KEY = "sleep_daily"
BODY_SYNC_KEY = "body_battery_daily"
MIN_SYNC_INTERVAL_MINUTES = 45
UK_TZ = ZoneInfo("Europe/London")


def _uk_now() -> dt.datetime:
    # UK local time behavior for sync windows (DST aware).
    return dt.datetime.now(dt.timezone.utc).astimezone(UK_TZ)


def _today() -> dt.date:
    return _uk_now().date()


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


def _sleep_window_open(now_local: dt.datetime) -> bool:
    return now_local.time() >= dt.time(hour=8, minute=0)


def _body_window_open(now_local: dt.datetime) -> bool:
    return now_local.time() >= dt.time(hour=23, minute=50)


def _get_int(d: Dict[str, Any], *keys: str) -> Optional[int]:
    def _get_nested_value(src: Dict[str, Any], key_path: str) -> Any:
        node: Any = src
        for part in key_path.split("."):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
            if node is None:
                return None
        return node

    for key in keys:
        v = _get_nested_value(d, key) if "." in key else d.get(key)
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    return None


def _to_datetime(ms_epoch: Optional[int]) -> Optional[dt.datetime]:
    if not ms_epoch:
        return None
    try:
        return dt.datetime.fromtimestamp(int(ms_epoch) / 1000, tz=dt.timezone.utc)
    except Exception:
        return None


def _upsert_sleep_daily(db: Session, sleep_date: dt.date, payload: Dict[str, Any]) -> models.GarminSleepDaily:
    row = db.query(models.GarminSleepDaily).filter(models.GarminSleepDaily.sleep_date == sleep_date).first()
    if not row:
        row = models.GarminSleepDaily(sleep_date=sleep_date)
        db.add(row)

    # Garmin wraps all metrics inside dailySleepDTO; fall back to top-level for safety
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

    # sleepScores.overall is a dict {"value": int, ...} in the current Garmin API
    sleep_scores = dto.get("sleepScores") or {}
    overall = sleep_scores.get("overall")
    if isinstance(overall, dict):
        row.sleep_score = overall.get("value")
    else:
        score = _get_int(dto, "overallSleepScore")
        row.sleep_score = score if score is not None else (int(overall) if overall is not None else None)

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

    # Different Garmin responses expose different keys; map defensively.
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


def sync_sleep_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    now_local = _uk_now()
    state = _get_sync_state(db, SLEEP_SYNC_KEY)

    logger.info(
        "Sleep sync requested; force=%s now_local=%s last_synced_at=%s",
        force,
        now_local.isoformat(),
        state.last_synced_at.isoformat() if state.last_synced_at else None,
    )

    if not is_garmin_configured():
        logger.warning("Sleep sync skipped: garmin_not_configured")
        return {"status": "skipped", "reason": "garmin_not_configured"}
    if not force and _recently_synced(state.last_synced_at):
        logger.info("Sleep sync skipped: throttled_recent_sync")
        return {"status": "skipped", "reason": "throttled_recent_sync"}
    if not force and not _sleep_window_open(now_local):
        logger.info("Sleep sync skipped: outside_sleep_sync_window")
        return {"status": "skipped", "reason": "outside_sleep_sync_window"}
    if not force and state.last_synced_at and state.last_synced_at.date() >= _today():
        logger.info("Sleep sync skipped: already_synced_today")
        return {"status": "skipped", "reason": "already_synced_today"}

    try:
        client = get_garmin_client()
        date_str = _today().isoformat()
        logger.info("Requesting Garmin sleep data; date=%s", date_str)
        payload = client.get_sleep_data(date_str) or {}
        logger.info("Received Garmin sleep payload; date=%s payload_keys=%s", date_str, sorted(payload.keys()))
        row = _upsert_sleep_daily(db, _today(), payload)
    except GarminRateLimitError:
        raise
    except GarminClientError as exc:
        logger.error("Sleep sync failed with Garmin client error: %s", exc)
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected sleep sync failure")
        return {"status": "error", "reason": f"sleep_sync_failed: {exc}"}

    state.last_synced_at = dt.datetime.now(dt.timezone.utc)
    state.detail = "sleep_sync_ok"
    db.commit()

    logger.info("Sleep sync complete; date=%s row_id=%s", row.sleep_date.isoformat(), row.id)

    return {"status": "ok", "sleep_date": row.sleep_date.isoformat(), "id": row.id}


def sync_body_battery_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    now_local = _uk_now()
    state = _get_sync_state(db, BODY_SYNC_KEY)

    logger.info(
        "Body battery sync requested; force=%s now_local=%s last_synced_at=%s",
        force,
        now_local.isoformat(),
        state.last_synced_at.isoformat() if state.last_synced_at else None,
    )

    if not is_garmin_configured():
        logger.warning("Body battery sync skipped: garmin_not_configured")
        return {"status": "skipped", "reason": "garmin_not_configured"}
    if not force and _recently_synced(state.last_synced_at):
        logger.info("Body battery sync skipped: throttled_recent_sync")
        return {"status": "skipped", "reason": "throttled_recent_sync"}
    if not force and not _body_window_open(now_local):
        logger.info("Body battery sync skipped: outside_body_sync_window")
        return {"status": "skipped", "reason": "outside_body_sync_window"}
    if not force and state.last_synced_at and state.last_synced_at.date() >= _today():
        logger.info("Body battery sync skipped: already_synced_today")
        return {"status": "skipped", "reason": "already_synced_today"}

    try:
        client = get_garmin_client()
        date_str = _today().isoformat()
        logger.info("Requesting Garmin body battery stats; date=%s", date_str)
        payload = client.get_stats(date_str) or {}
        logger.info("Received Garmin body battery payload; date=%s payload_keys=%s", date_str, sorted(payload.keys()))
        row = _upsert_body_daily(db, _today(), payload)
    except GarminRateLimitError:
        raise
    except GarminClientError as exc:
        logger.error("Body battery sync failed with Garmin client error: %s", exc)
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected body battery sync failure")
        return {"status": "error", "reason": f"body_sync_failed: {exc}"}

    state.last_synced_at = dt.datetime.now(dt.timezone.utc)
    state.detail = "body_sync_ok"
    db.commit()

    logger.info("Body battery sync complete; date=%s row_id=%s", row.battery_date.isoformat(), row.id)

    return {"status": "ok", "battery_date": row.battery_date.isoformat(), "id": row.id}


def sync_smart(db: Session, force: bool = False) -> Dict[str, Any]:
    logger.info("Smart Garmin sync requested; force=%s", force)
    sleep_result = sync_sleep_if_due(db, force=force)
    body_result = sync_body_battery_if_due(db, force=force)
    logger.info("Smart Garmin sync finished; sleep=%s body_battery=%s", sleep_result, body_result)
    return {
        "sleep": sleep_result,
        "body_battery": body_result,
    }
