import datetime as dt
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..garmin_client import GarminClientError, get_garmin_client, is_garmin_configured
from .. import models

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

    row.sleep_start = _to_datetime(_get_int(payload, "sleepStartTimestampGMT", "sleepStartTimestampLocal"))
    row.sleep_end = _to_datetime(_get_int(payload, "sleepEndTimestampGMT", "sleepEndTimestampLocal"))
    row.total_sleep_minutes = _get_int(payload, "sleepTimeSeconds", "totalSleepSeconds")
    if row.total_sleep_minutes is not None:
        row.total_sleep_minutes = row.total_sleep_minutes // 60

    row.deep_sleep_minutes = _get_int(payload, "deepSleepSeconds")
    row.light_sleep_minutes = _get_int(payload, "lightSleepSeconds")
    row.rem_sleep_minutes = _get_int(payload, "remSleepSeconds")
    row.awake_minutes = _get_int(payload, "awakeSleepSeconds")

    if row.deep_sleep_minutes is not None:
        row.deep_sleep_minutes = row.deep_sleep_minutes // 60
    if row.light_sleep_minutes is not None:
        row.light_sleep_minutes = row.light_sleep_minutes // 60
    if row.rem_sleep_minutes is not None:
        row.rem_sleep_minutes = row.rem_sleep_minutes // 60
    if row.awake_minutes is not None:
        row.awake_minutes = row.awake_minutes // 60

    row.sleep_score = _get_int(payload, "overallSleepScore", "sleepScores.overallScore", "sleepScores.overall")
    row.body_battery_wakeup = _get_int(payload, "bodyBatteryWakeup")
    row.body_battery_bedtime = _get_int(payload, "bodyBatteryBedtime")
    row.payload = payload

    db.commit()
    db.refresh(row)
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
    return row


def sync_sleep_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    now_local = _uk_now()
    state = _get_sync_state(db, SLEEP_SYNC_KEY)

    if not is_garmin_configured():
        return {"status": "skipped", "reason": "garmin_not_configured"}
    if not force and _recently_synced(state.last_synced_at):
        return {"status": "skipped", "reason": "throttled_recent_sync"}
    if not force and not _sleep_window_open(now_local):
        return {"status": "skipped", "reason": "outside_sleep_sync_window"}
    if not force and state.last_synced_at and state.last_synced_at.date() >= _today():
        return {"status": "skipped", "reason": "already_synced_today"}

    try:
        client = get_garmin_client()
        date_str = _today().isoformat()
        payload = client.get_sleep_data(date_str) or {}
        row = _upsert_sleep_daily(db, _today(), payload)
    except GarminClientError as exc:
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        return {"status": "error", "reason": f"sleep_sync_failed: {exc}"}

    state.last_synced_at = dt.datetime.now(dt.timezone.utc)
    state.detail = "sleep_sync_ok"
    db.commit()

    return {"status": "ok", "sleep_date": row.sleep_date.isoformat(), "id": row.id}


def sync_body_battery_if_due(db: Session, force: bool = False) -> Dict[str, Any]:
    now_local = _uk_now()
    state = _get_sync_state(db, BODY_SYNC_KEY)

    if not is_garmin_configured():
        return {"status": "skipped", "reason": "garmin_not_configured"}
    if not force and _recently_synced(state.last_synced_at):
        return {"status": "skipped", "reason": "throttled_recent_sync"}
    if not force and not _body_window_open(now_local):
        return {"status": "skipped", "reason": "outside_body_sync_window"}
    if not force and state.last_synced_at and state.last_synced_at.date() >= _today():
        return {"status": "skipped", "reason": "already_synced_today"}

    try:
        client = get_garmin_client()
        date_str = _today().isoformat()
        payload = client.get_stats(date_str) or {}
        row = _upsert_body_daily(db, _today(), payload)
    except GarminClientError as exc:
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        return {"status": "error", "reason": f"body_sync_failed: {exc}"}

    state.last_synced_at = dt.datetime.now(dt.timezone.utc)
    state.detail = "body_sync_ok"
    db.commit()

    return {"status": "ok", "battery_date": row.battery_date.isoformat(), "id": row.id}


def sync_smart(db: Session, force: bool = False) -> Dict[str, Any]:
    sleep_result = sync_sleep_if_due(db, force=force)
    body_result = sync_body_battery_if_due(db, force=force)
    return {
        "sleep": sleep_result,
        "body_battery": body_result,
    }
