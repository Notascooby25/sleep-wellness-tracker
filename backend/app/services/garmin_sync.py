import datetime as dt
import logging
import os
import statistics
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
STEPS_SYNC_KEY = "steps_daily"
ACTIVITY_SYNC_KEY = "activities"
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
STEPS_BACKFILL_DAYS = _env_int("GARMIN_STEPS_BACKFILL_DAYS", 7)
ACTIVITY_BACKFILL_DAYS = _env_int("GARMIN_ACTIVITY_BACKFILL_DAYS", 30)


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


def _parse_datetime(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None

    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)

    if isinstance(value, (int, float)):
        raw = int(value)
        # Heuristic: Garmin sometimes returns epoch milliseconds, sometimes seconds.
        if raw > 10_000_000_000:
            raw = raw // 1000
        try:
            return dt.datetime.fromtimestamp(raw, tz=dt.timezone.utc)
        except Exception:
            return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
        except Exception:
            return None

    return None


def _normalize_activity_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    compact = value.strip()
    if not compact:
        return None
    return compact.replace("_", " ").title()


def _activity_id(payload: Dict[str, Any], default_index: int) -> str:
    raw = _get_text(
        payload,
        "activityId",
        "activityUUID",
        "activityUuid",
        "uuid",
        "summaryId",
    )
    if raw:
        return raw
    fallback_bits = [
        _get_text(payload, "startTimeGMT", "startTimeLocal", "startTime", "startDate"),
        _get_text(payload, "activityName", "activityType.typeKey", "activityTypeDTO.typeKey"),
        str(_get_int(payload, "duration", "durationInSeconds") or ""),
    ]
    joined = "|".join(bit for bit in fallback_bits if bit)
    return joined or f"unknown-{default_index}"


def _normalize_activities_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ["activities", "activityList", "results"]:
            val = payload.get(key)
            if isinstance(val, list):
                return [row for row in val if isinstance(row, dict)]
        return [payload]
    return []


def _extract_activity_start(payload: Dict[str, Any]) -> Optional[dt.datetime]:
    nested = payload.get("summaryDTO") if isinstance(payload.get("summaryDTO"), dict) else {}

    start = _parse_datetime(
        _get_value(
            payload,
            "startTimeGMT",
            "startTimeLocal",
            "startTime",
            "startDate",
            "beginTimestamp",
            "startTimeInMillis",
            "startTimeInSeconds",
        )
    )
    if start:
        return start

    return _parse_datetime(
        _get_value(
            nested,
            "startTimeGMT",
            "startTimeLocal",
            "startTimeInMillis",
            "startTimeInSeconds",
        )
    )


def _filter_activity_rows(rows: List[Dict[str, Any]], start_date: dt.date, end_date: dt.date) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        start = _extract_activity_start(row)
        if not start:
            filtered.append(row)
            continue
        d = start.astimezone(UK_TZ).date()
        if start_date <= d <= end_date:
            filtered.append(row)
    return filtered


def _fetch_activities_payload(client: Any, start_date: dt.date, end_date: dt.date) -> List[Dict[str, Any]]:
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    ranged_methods = ["get_activities_by_date", "get_activities_by_dates", "get_activities_for_date_range"]
    for method_name in ranged_methods:
        method = getattr(client, method_name, None)
        if not callable(method):
            continue
        for args in [(start_iso, end_iso), (start_date, end_date), (start_iso, end_iso, 0, 500)]:
            try:
                rows = _normalize_activities_payload(method(*args))
                if rows:
                    return _filter_activity_rows(rows, start_date, end_date)
            except TypeError:
                continue

    per_day_methods = ["get_activities_fordate", "get_activities_for_date"]
    gathered: List[Dict[str, Any]] = []
    for method_name in per_day_methods:
        method = getattr(client, method_name, None)
        if not callable(method):
            continue
        for target_date in _recent_dates((end_date - start_date).days + 1, end_date=end_date):
            date_str = target_date.isoformat()
            try:
                gathered.extend(_normalize_activities_payload(method(date_str)))
            except TypeError:
                continue
        if gathered:
            return _filter_activity_rows(gathered, start_date, end_date)

    method = getattr(client, "get_activities", None)
    if callable(method):
        page = 0
        page_size = 100
        paged_rows: List[Dict[str, Any]] = []
        for _ in range(20):
            try:
                batch = _normalize_activities_payload(method(page * page_size, page_size))
            except TypeError:
                batch = _normalize_activities_payload(method())
            if not batch:
                break
            paged_rows.extend(batch)
            oldest_in_batch = None
            for item in batch:
                start = _extract_activity_start(item)
                if start:
                    candidate = start.astimezone(UK_TZ).date()
                    if oldest_in_batch is None or candidate < oldest_in_batch:
                        oldest_in_batch = candidate
            if oldest_in_batch and oldest_in_batch < start_date:
                break
            if len(batch) < page_size:
                break
            page += 1
        return _filter_activity_rows(paged_rows, start_date, end_date)

    raise GarminClientError("Garmin client does not support activity retrieval methods")


def _upsert_activity(db: Session, payload: Dict[str, Any], fallback_index: int) -> Optional[models.GarminActivity]:
    activity_start = _extract_activity_start(payload)
    if not activity_start:
        logger.warning("Skipping Garmin activity without start time; payload_keys=%s", sorted(payload.keys()))
        return None

    activity_date = activity_start.astimezone(UK_TZ).date()
    garmin_activity_id = _activity_id(payload, fallback_index)

    row = (
        db.query(models.GarminActivity)
        .filter(models.GarminActivity.garmin_activity_id == garmin_activity_id)
        .first()
    )
    if not row:
        row = models.GarminActivity(garmin_activity_id=garmin_activity_id, activity_date=activity_date)
        db.add(row)

    nested = payload.get("summaryDTO") if isinstance(payload.get("summaryDTO"), dict) else {}
    row.activity_date = activity_date
    row.start_time = activity_start
    row.activity_type = _normalize_activity_type(
        _get_text(
            payload,
            "activityType.typeKey",
            "activityTypeDTO.typeKey",
            "activityType.typeName",
            "activityType",
        )
    )
    row.activity_name = _get_text(payload, "activityName", "activity_type", "activityType.typeName")
    row.distance_meters = _get_int(payload, "distance", "distanceInMeters", "distanceMeters")
    if row.distance_meters is None:
        row.distance_meters = _get_int(nested, "distance")
    row.duration_seconds = _get_int(
        payload,
        "duration",
        "durationInSeconds",
        "movingDuration",
        "movingDurationInSeconds",
        "elapsedDuration",
        "elapsedDurationInSeconds",
    )
    if row.duration_seconds is None:
        row.duration_seconds = _get_int(nested, "duration", "movingDurationInSeconds")
    row.calories = _get_int(payload, "calories", "activeKilocalories", "totalKilocalories")
    if row.calories is None:
        row.calories = _get_int(nested, "calories")
    row.average_hr = _get_int(payload, "averageHR", "averageHeartRate", "avgHr")
    if row.average_hr is None:
        row.average_hr = _get_int(nested, "averageHR", "averageHeartRate")
    row.max_hr = _get_int(payload, "maxHR", "maxHeartRate")
    if row.max_hr is None:
        row.max_hr = _get_int(nested, "maxHR", "maxHeartRate")
    row.payload = payload

    return row


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

    row.morning_value = _get_int(payload, "morningValue", "bodyBatteryMorning")
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

    row.overall_stress_level = _get_int(payload, "overallStressLevel", "averageStressLevel", "avgStressLevel", "stressLevel")

    # Garmin payload variants expose duration fields under different names and units.
    rest_minutes = _get_int(
        payload,
        "restStressDuration",
        "restDuration",
        "restStressDurationInMinutes",
    )
    low_minutes = _get_int(
        payload,
        "lowStressDuration",
        "lowDuration",
        "lowStressDurationInMinutes",
    )
    medium_minutes = _get_int(
        payload,
        "mediumStressDuration",
        "mediumDuration",
        "mediumStressDurationInMinutes",
    )
    high_minutes = _get_int(
        payload,
        "highStressDuration",
        "highDuration",
        "highStressDurationInMinutes",
    )

    # Some Garmin payloads provide seconds instead of minutes.
    rest_seconds = _get_int(payload, "restStressDurationInSeconds", "restDurationInSeconds")
    low_seconds = _get_int(payload, "lowStressDurationInSeconds", "lowDurationInSeconds")
    medium_seconds = _get_int(payload, "mediumStressDurationInSeconds", "mediumDurationInSeconds")
    high_seconds = _get_int(payload, "highStressDurationInSeconds", "highDurationInSeconds")

    if rest_minutes is None and rest_seconds is not None:
        rest_minutes = rest_seconds // 60
    if low_minutes is None and low_seconds is not None:
        low_minutes = low_seconds // 60
    if medium_minutes is None and medium_seconds is not None:
        medium_minutes = medium_seconds // 60
    if high_minutes is None and high_seconds is not None:
        high_minutes = high_seconds // 60

    row.rest_stress_duration = rest_minutes
    row.low_stress_duration = low_minutes
    row.medium_stress_duration = medium_minutes
    row.high_stress_duration = high_minutes

    # Garmin stress payloads commonly return stressValuesArray + avg/max levels instead of explicit duration fields.
    # When durations are missing, derive rough buckets from stress values so the UI does not show n/a everywhere.
    stress_values = payload.get("stressValuesArray")
    if isinstance(stress_values, list) and any(
        value is None
        for value in [row.rest_stress_duration, row.low_stress_duration, row.medium_stress_duration, row.high_stress_duration]
    ):
        rest_minutes_derived, low_minutes_derived, medium_minutes_derived, high_minutes_derived = _derive_stress_minutes(stress_values)

        if row.rest_stress_duration is None:
            row.rest_stress_duration = rest_minutes_derived
        if row.low_stress_duration is None:
            row.low_stress_duration = low_minutes_derived
        if row.medium_stress_duration is None:
            row.medium_stress_duration = medium_minutes_derived
        if row.high_stress_duration is None:
            row.high_stress_duration = high_minutes_derived

    if row.overall_stress_level is None:
        row.overall_stress_level = _get_int(payload, "maxStressLevel")

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


def _derive_stress_minutes(stress_values: List[Any]) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    timestamps_ms: List[int] = []
    levels: List[int] = []

    for item in stress_values:
        level: Optional[int] = None
        timestamp: Optional[int] = None

        if isinstance(item, (int, float)):
            level = int(item)
        elif isinstance(item, dict):
            level = _get_int(item, "stressLevel", "value", "level")
            timestamp = _get_int(
                item,
                "timestamp",
                "timeInMillis",
                "measurementTimeInMillis",
                "startTimeInMillis",
                "startGMT",
                "startTimestampGMT",
            )
        elif isinstance(item, (list, tuple)) and item:
            if len(item) >= 2:
                first = item[0]
                second = item[1]
                if isinstance(first, (int, float)) and isinstance(second, (int, float)):
                    if first > 10_000_000_000:
                        timestamp = int(first)
                        level = int(second)
                    else:
                        level = int(first)
                        timestamp = int(second) if second > 10_000_000_000 else None
            elif len(item) == 1 and isinstance(item[0], (int, float)):
                level = int(item[0])

        if level is None or level < 0:
            continue

        levels.append(level)
        if timestamp is not None and timestamp > 0:
            timestamps_ms.append(timestamp)

    if not levels:
        return None, None, None, None

    sample_minutes = 1.0
    if len(timestamps_ms) >= 3:
        sorted_ts = sorted(set(timestamps_ms))
        deltas = [
            (sorted_ts[idx] - sorted_ts[idx - 1]) / 60000.0
            for idx in range(1, len(sorted_ts))
            if sorted_ts[idx] > sorted_ts[idx - 1]
        ]
        if deltas:
            sample_minutes = max(1.0, min(15.0, statistics.median(deltas)))

    rest_count = 0
    low_count = 0
    medium_count = 0
    high_count = 0

    for level in levels:
        # Some Garmin payloads use categorical values 0/1/2/3, others use a 0..100 scale.
        if level in (0, 1, 2, 3):
            if level == 0:
                rest_count += 1
            elif level == 1:
                low_count += 1
            elif level == 2:
                medium_count += 1
            else:
                high_count += 1
            continue

        if level == 0:
            rest_count += 1
        elif level <= 25:
            low_count += 1
        elif level <= 50:
            medium_count += 1
        else:
            high_count += 1

    def _to_minutes(count: int) -> Optional[int]:
        if count <= 0:
            return None
        return int(round(count * sample_minutes))

    return _to_minutes(rest_count), _to_minutes(low_count), _to_minutes(medium_count), _to_minutes(high_count)


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


def _upsert_steps_daily(db: Session, steps_date: dt.date, payload: Dict[str, Any]) -> models.GarminStepsDaily:
    row = db.query(models.GarminStepsDaily).filter(models.GarminStepsDaily.steps_date == steps_date).first()
    if not row:
        row = models.GarminStepsDaily(steps_date=steps_date)
        db.add(row)

    row.total_steps = _get_int(
        payload,
        "totalSteps",
        "steps",
        "dailyStepDTO.totalSteps",
        "dailySteps",
        "allDaySteps",
        "stepCount",
    )
    row.distance_meters = _get_int(
        payload,
        "distanceInMeters",
        "totalDistanceMeters",
        "distanceMeters",
        "dailyStepDTO.distanceInMeters",
        "dailyStepDTO.totalDistanceMeters",
        "distance",
    )
    row.calories_burned = _get_int(
        payload,
        "caloriesBurned",
        "activeKilocalories",
        "dailyStepDTO.caloriesBurned",
        "calories",
    )
    row.payload = payload

    db.commit()
    db.refresh(row)
    logger.info(
        "Upserted Garmin steps row; date=%s total_steps=%s payload_keys=%s",
        steps_date.isoformat(),
        row.total_steps,
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
    return _call_client_method(client, ["get_stress_data", "get_all_day_stress", "get_stress", "get_stress_stats"], date_str)


def _fetch_hydration_payload(client: Any, date_str: str) -> Dict[str, Any]:
    return _call_client_method(client, ["get_hydration_data", "get_hydration", "get_hydration_stats"], date_str)


def _fetch_steps_payload(client: Any, date_str: str) -> Dict[str, Any]:
    def _normalize(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            if not raw:
                return {}
            if all(isinstance(item, dict) for item in raw):
                merged: Dict[str, Any] = {}
                for item in raw:
                    merged.update(item)
                if "totalSteps" not in merged:
                    merged["totalSteps"] = _get_int({"v": sum(_get_int(item, "steps", "stepCount") or 0 for item in raw)}, "v")
                return merged
            numeric_items = [int(item) for item in raw if isinstance(item, (int, float))]
            if numeric_items:
                return {"totalSteps": sum(numeric_items)}
        return {}

    candidates = ["get_steps_data", "get_daily_steps", "get_steps", "get_stats"]
    for method_name in candidates:
        method = getattr(client, method_name, None)
        if not callable(method):
            continue
        for args in [(date_str,), (date_str, date_str), tuple()]:
            try:
                payload = _normalize(method(*args))
                if payload:
                    return payload
            except TypeError:
                continue
    raise GarminClientError("Garmin client does not support steps retrieval methods")


def _sync_activities_window(
    client: Any,
    db: Session,
    start_date: dt.date,
    end_date: dt.date,
) -> Tuple[List[str], List[Dict[str, str]]]:
    synced_dates: List[str] = []
    failed_dates: List[Dict[str, str]] = []
    seen_dates: set[str] = set()

    try:
        logger.info("Requesting Garmin activities; start_date=%s end_date=%s", start_date.isoformat(), end_date.isoformat())
        rows = _fetch_activities_payload(client, start_date, end_date)
    except Exception as exc:
        logger.exception("Failed retrieving Garmin activities")
        return synced_dates, [{"date": f"{start_date.isoformat()}..{end_date.isoformat()}", "error": str(exc)}]

    for idx, payload in enumerate(rows, start=1):
        try:
            row = _upsert_activity(db, payload, idx)
            if row is None:
                continue
            seen_dates.add(row.activity_date.isoformat())
        except Exception as exc:
            activity_id = _activity_id(payload, idx)
            logger.exception("Failed upserting Garmin activity; garmin_activity_id=%s", activity_id)
            failed_dates.append({"date": activity_id, "error": str(exc)})

    if seen_dates:
        db.commit()
        synced_dates = sorted(seen_dates)

    logger.info(
        "Garmin activities sync complete; activities=%s date_count=%s failed=%s",
        len(rows),
        len(synced_dates),
        len(failed_dates),
    )
    return synced_dates, failed_dates


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


def _sync_steps_dates(client: Any, db: Session, dates: List[dt.date]) -> Tuple[List[str], List[Dict[str, str]]]:
    return _sync_metric_dates(client, db, dates, "steps", _fetch_steps_payload, _upsert_steps_daily)


def _run_metric_sync(
    db: Session,
    *,
    force: bool,
    state_key: str,
    metric_name: str,
    backfill_days: int,
    backfill_days_override: Optional[int],
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

    effective_backfill_days = max(1, int(backfill_days_override)) if backfill_days_override else backfill_days

    try:
        client = get_garmin_client()
        target_dates = _recent_dates(effective_backfill_days)
        logger.info(
            "Running Garmin %s backfill; days=%s start_date=%s end_date=%s",
            metric_name,
            effective_backfill_days,
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
        "backfill_days": effective_backfill_days,
    }


def sync_sleep_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=SLEEP_SYNC_KEY,
        metric_name="sleep",
        backfill_days=SLEEP_BACKFILL_DAYS,
        backfill_days_override=backfill_days,
        sync_dates_fn=_sync_sleep_dates,
        latest_field="sleep_date",
        window_open=_recovery_window_open,
        skipped_reason="outside_sleep_sync_window",
    )


def sync_body_battery_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=BODY_SYNC_KEY,
        metric_name="body battery",
        backfill_days=BODY_BACKFILL_DAYS,
        backfill_days_override=backfill_days,
        sync_dates_fn=_sync_body_dates,
        latest_field="battery_date",
        window_open=_day_close_window_open,
        skipped_reason="outside_body_sync_window",
    )


def sync_hrv_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=HRV_SYNC_KEY,
        metric_name="hrv",
        backfill_days=HRV_BACKFILL_DAYS,
        backfill_days_override=backfill_days,
        sync_dates_fn=_sync_hrv_dates,
        latest_field="hrv_date",
        window_open=_recovery_window_open,
        skipped_reason="outside_hrv_sync_window",
    )


def sync_resting_heart_rate_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=RHR_SYNC_KEY,
        metric_name="resting heart rate",
        backfill_days=RHR_BACKFILL_DAYS,
        backfill_days_override=backfill_days,
        sync_dates_fn=_sync_rhr_dates,
        latest_field="heart_rate_date",
        window_open=_recovery_window_open,
        skipped_reason="outside_rhr_sync_window",
    )


def sync_stress_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=STRESS_SYNC_KEY,
        metric_name="stress",
        backfill_days=STRESS_BACKFILL_DAYS,
        backfill_days_override=backfill_days,
        sync_dates_fn=_sync_stress_dates,
        latest_field="stress_date",
        window_open=_day_close_window_open,
        skipped_reason="outside_stress_sync_window",
    )


def sync_hydration_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=HYDRATION_SYNC_KEY,
        metric_name="hydration",
        backfill_days=HYDRATION_BACKFILL_DAYS,
        backfill_days_override=backfill_days,
        sync_dates_fn=_sync_hydration_dates,
        latest_field="hydration_date",
        window_open=_day_close_window_open,
        skipped_reason="outside_hydration_sync_window",
    )


def sync_steps_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    return _run_metric_sync(
        db,
        force=force,
        state_key=STEPS_SYNC_KEY,
        metric_name="steps",
        backfill_days=STEPS_BACKFILL_DAYS,
        backfill_days_override=backfill_days,
        sync_dates_fn=_sync_steps_dates,
        latest_field="steps_date",
        window_open=_day_close_window_open,
        skipped_reason="outside_steps_sync_window",
    )


def sync_activities_if_due(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    now_local = _uk_now()
    state = _get_sync_state(db, ACTIVITY_SYNC_KEY)

    logger.info(
        "activities sync requested; force=%s now_local=%s last_synced_at=%s",
        force,
        now_local.isoformat(),
        state.last_synced_at.isoformat() if state.last_synced_at else None,
    )

    if not is_garmin_configured():
        logger.warning("activities sync skipped: garmin_not_configured")
        return {"status": "skipped", "reason": "garmin_not_configured"}
    if not force and _recently_synced(state.last_synced_at):
        logger.info("activities sync skipped: throttled_recent_sync")
        return {"status": "skipped", "reason": "throttled_recent_sync"}
    if not force and state.last_synced_at and state.last_synced_at.date() >= _today():
        logger.info("activities sync skipped: already_synced_today")
        return {"status": "skipped", "reason": "already_synced_today"}

    effective_backfill_days = max(1, int(backfill_days_override)) if (backfill_days_override := backfill_days) else ACTIVITY_BACKFILL_DAYS
    end_date = _today()
    start_date = end_date - dt.timedelta(days=effective_backfill_days - 1)

    try:
        client = get_garmin_client()
        synced_dates, failed_dates = _sync_activities_window(client, db, start_date, end_date)
    except GarminRateLimitError:
        raise
    except GarminClientError as exc:
        logger.error("activities sync failed with Garmin client error: %s", exc)
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected activities sync failure")
        return {"status": "error", "reason": f"{ACTIVITY_SYNC_KEY}_sync_failed: {exc}"}

    if not synced_dates and failed_dates:
        return {
            "status": "error",
            "reason": f"{ACTIVITY_SYNC_KEY}_backfill_failed",
            "failed_dates": failed_dates,
        }

    state.last_synced_at = dt.datetime.now(dt.timezone.utc)
    state.detail = f"{ACTIVITY_SYNC_KEY}_partial" if failed_dates else f"{ACTIVITY_SYNC_KEY}_ok"
    db.commit()

    return {
        "status": "partial" if failed_dates else "ok",
        "activity_date": synced_dates[-1] if synced_dates else None,
        "synced_dates": synced_dates,
        "failed_dates": failed_dates,
        "backfill_days": effective_backfill_days,
    }


def sync_smart(db: Session, force: bool = False, backfill_days: Optional[int] = None) -> Dict[str, Any]:
    logger.info("Smart Garmin sync requested; force=%s backfill_days=%s", force, backfill_days)
    results = {
        "sleep": sync_sleep_if_due(db, force=force, backfill_days=backfill_days),
        "body_battery": sync_body_battery_if_due(db, force=force, backfill_days=backfill_days),
        "hrv": sync_hrv_if_due(db, force=force, backfill_days=backfill_days),
        "resting_heart_rate": sync_resting_heart_rate_if_due(db, force=force, backfill_days=backfill_days),
        "stress": sync_stress_if_due(db, force=force, backfill_days=backfill_days),
        "hydration": sync_hydration_if_due(db, force=force, backfill_days=backfill_days),
        "steps": sync_steps_if_due(db, force=force, backfill_days=backfill_days),
        "activities": sync_activities_if_due(db, force=force, backfill_days=backfill_days),
    }
    logger.info("Smart Garmin sync finished; results=%s", results)
    return results
