import datetime as dt
import json
import math
import statistics
from collections import defaultdict

from sqlalchemy.orm import Session, selectinload

from .. import models
from .comparison import CONFIDENCE_ORDER, MIN_NIGHTS, bh_adjust, compare, is_negligible, level_for
from .insight_dates import UK_TZ, is_late_workout, night_for_entry, night_for_workout
from .item_roles import (
    ACUPUNCTURE_PAGE,
    effective_role,
    is_before_sleep,
    is_hidden_on,
    is_symptom,
    role_was_set_by_owner,
)

TRIGGER_WINDOWS = ("period", "90d", "all")
MIN_BINARY_EFFECT_PCT = 5
WORKOUT_LABEL = "Workout (day before)"
LATE_WORKOUT_LABEL = "Late workout (after 6pm, day before)"
LONG_WORKOUT_LABEL = "Long workout (> 45m, day before)"
MAX_REPORT_RANGE_DAYS = 731
EARLIEST_REPORT_DATE = dt.date(2000, 1, 1)
LATEST_REPORT_DATE = dt.date(2100, 12, 31)


def _check_report_range(start_date: dt.date, end_date: dt.date) -> None:
    """Reject ranges the report can't sensibly show (also stops a huge day-by-day timeline)."""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if start_date < EARLIEST_REPORT_DATE or end_date > LATEST_REPORT_DATE:
        raise ValueError("dates must be between 2000-01-01 and 2100-12-31")
    if (end_date - start_date).days + 1 > MAX_REPORT_RANGE_DAYS:
        raise ValueError(f"date range must be {MAX_REPORT_RANGE_DAYS} days or fewer")


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _dig(payload, *paths: tuple[str, ...]) -> float | None:
    for path in paths:
        current = payload
        for key in path:
            current = current.get(key) if isinstance(current, dict) else None
        number = _number(current)
        if number is not None:
            return number
    return None


def _normalize_positions(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            parsed = [value]
        candidates = parsed if isinstance(parsed, list) else [str(parsed)]
    else:
        candidates = [str(value)]
    positions: list[str] = []
    for candidate in candidates:
        label = str(candidate).strip()
        if label and label not in positions:
            positions.append(label)
    return positions


def _is_migraine_name(name: str | None) -> bool:
    return "migraine" in (name or "").strip().lower()


# When a headache started, as UK local time. Same-day items logged from this time on
# came after the headache began, so they can't have caused it.
ONSET_CUTOFFS = {
    "woke": dt.time(0, 0),
    "morning": dt.time(6, 0),
    "afternoon": dt.time(12, 0),
    "evening": dt.time(17, 0),
}


def _load_headache_checks(db: Session, start: dt.date, end: dt.date) -> dict[dt.date, models.HeadacheCheck]:
    """The owner's daily yes/no answers. Where one exists it decides the day, whatever was tapped."""
    rows = (
        db.query(models.HeadacheCheck)
        .filter(models.HeadacheCheck.check_date >= start, models.HeadacheCheck.check_date <= end)
        .all()
    )
    return {row.check_date: row for row in rows}


def _apply_checks(symptom_days: set[dt.date], checks: dict[dt.date, models.HeadacheCheck]) -> set[dt.date]:
    result = set(symptom_days)
    for day, check in checks.items():
        if check.had_headache:
            result.add(day)
        else:
            result.discard(day)
    return result


def _logged_after_onset(logged_at: dt.datetime, check: models.HeadacheCheck | None) -> bool:
    if check is None or not check.had_headache or check.onset not in ONSET_CUTOFFS:
        return False
    return logged_at.astimezone(UK_TZ).time() >= ONSET_CUTOFFS[check.onset]


def _group_old_and_current_copies(
    db: Session, logged: dict[int, models.Activity]
) -> list[tuple[models.Activity, list[models.Activity]]]:
    if not logged:
        return []
    names = {(a.name or "").strip().lower() for a in logged.values()}
    same_named: dict[str, list[models.Activity]] = defaultdict(list)
    for activity in db.query(models.Activity).options(selectinload(models.Activity.category)).all():
        key = (activity.name or "").strip().lower()
        if key in names:
            same_named[key].append(activity)

    primary_of: dict[int, models.Activity] = {}
    for copies in same_named.values():
        current = [a for a in copies if a.deprecated_at is None]
        fallback = max(current or copies, key=lambda a: a.id)
        for activity in copies:
            primary_of[activity.id] = activity if activity.deprecated_at is None and len(current) > 1 else fallback

    members: dict[int, list[models.Activity]] = defaultdict(list)
    primaries: dict[int, models.Activity] = {}
    for activity_id, activity in logged.items():
        primary = primary_of.get(activity_id, activity)
        primaries[primary.id] = primary
        members[primary.id].append(activity)
    return [(primaries[pid], copies) for pid, copies in members.items()]


def get_acupuncture_session_dates(db: Session) -> list[dt.date]:
    activities = db.query(models.Activity).filter(models.Activity.name.ilike("%acupuncture%")).all()
    if not activities:
        return []
    activity_ids = [a.id for a in activities]
    moods = (
        db.query(models.Mood.timestamp)
        .join(models.mood_activities)
        .filter(models.mood_activities.c.activity_id.in_(activity_ids))
        .all()
    )
    return sorted({ts.astimezone(UK_TZ).date() for (ts,) in moods}, reverse=True)


def _resolve_prior_period(
    db: Session,
    start_date: dt.date,
    end_date: dt.date,
    session_dates: list[dt.date],
) -> dict | None:
    total_days = (end_date - start_date).days + 1
    session_set = set(session_dates)
    anchor = start_date - dt.timedelta(days=1)
    has_newer_inside = any(start_date <= s < end_date for s in session_dates)
    earlier_sessions = [s for s in session_dates if s < anchor]

    if anchor in session_set and not has_newer_inside and earlier_sessions:
        prev_start = earlier_sessions[0] + dt.timedelta(days=1)
        prev_end = anchor
        comparison_type = "previous_session_gap"
    else:
        prev_end = start_date - dt.timedelta(days=1)
        prev_start = prev_end - dt.timedelta(days=total_days - 1)
        comparison_type = "equal_length_prior"

    prior_from = dt.datetime.combine(prev_start, dt.time(), tzinfo=UK_TZ)
    prior_to = dt.datetime.combine(prev_end + dt.timedelta(days=1), dt.time(), tzinfo=UK_TZ)
    prior_moods = (
        db.query(models.Mood)
        .options(selectinload(models.Mood.activities).selectinload(models.Activity.category))
        .filter(models.Mood.timestamp >= prior_from, models.Mood.timestamp < prior_to)
        .all()
    )
    prior_checks = _load_headache_checks(db, prev_start, prev_end)
    if not prior_moods and not prior_checks:
        return None

    prior_symptom_days: set[dt.date] = set()
    for mood in prior_moods:
        m_date = mood.timestamp.astimezone(UK_TZ).date()
        if prev_start <= m_date <= prev_end and any(is_symptom(act) for act in mood.activities):
            prior_symptom_days.add(m_date)
    prior_symptom_days = _apply_checks(prior_symptom_days, prior_checks)

    prior_total = max(1, (prev_end - prev_start).days + 1)
    return {
        "start_date": prev_start.isoformat(),
        "end_date": prev_end.isoformat(),
        "total_days": prior_total,
        "symptom_days": len(prior_symptom_days),
        "frequency": round((len(prior_symptom_days) / prior_total) * 100),
        "comparison_type": comparison_type,
    }


def compute_appointment_summary(
    db: Session,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> dict:
    today = dt.datetime.now(UK_TZ).date()
    end_date = end_date or today
    start_date = start_date or (end_date - dt.timedelta(days=29))
    _check_report_range(start_date, end_date)

    total_days = (end_date - start_date).days + 1
    session_dates = get_acupuncture_session_dates(db)
    session_set = set(session_dates)

    mood_from = dt.datetime.combine(start_date, dt.time(), tzinfo=UK_TZ)
    mood_to = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time(), tzinfo=UK_TZ)
    moods = (
        db.query(models.Mood)
        .options(
            selectinload(models.Mood.activities).selectinload(models.Activity.category),
            selectinload(models.Mood.activity_details),
        )
        .filter(models.Mood.timestamp >= mood_from, models.Mood.timestamp < mood_to)
        .all()
    )

    symptom_days: set[dt.date] = set()
    symptom_severities: list[float] = []
    symptom_activities_by_id: dict[int, models.Activity] = {}
    symptom_activity_days: dict[int, set[dt.date]] = defaultdict(set)
    position_days: dict[str, set[dt.date]] = defaultdict(set)
    day_raw_activities: dict[dt.date, set[int]] = defaultdict(set)
    day_positions: dict[dt.date, set[str]] = defaultdict(set)

    for mood in moods:
        mood_date = mood.timestamp.astimezone(UK_TZ).date()
        if not (start_date <= mood_date <= end_date):
            continue

        details_by_activity: dict[int, list[models.MoodActivityDetail]] = defaultdict(list)
        for det in mood.activity_details:
            details_by_activity[det.activity_id].append(det)

        for activity in mood.activities:
            if not is_symptom(activity):
                continue
            symptom_days.add(mood_date)
            symptom_activities_by_id[activity.id] = activity
            symptom_activity_days[activity.id].add(mood_date)
            day_raw_activities[mood_date].add(activity.id)

            for det in details_by_activity.get(activity.id, ()):
                if det.severity is not None:
                    symptom_severities.append(float(det.severity))
                for pos in _normalize_positions(det.position):
                    position_days[pos].add(mood_date)
                    day_positions[mood_date].add(pos)

    checks = _load_headache_checks(db, start_date, end_date)
    symptom_days = _apply_checks(symptom_days, checks)

    grouped_symptoms = _group_old_and_current_copies(db, symptom_activities_by_id)
    primary_name_by_id: dict[int, str] = {}
    symptom_breakdown: list[dict] = []
    for primary, copies in grouped_symptoms:
        name = (primary.name or "").strip()
        days_union = set().union(*(symptom_activity_days[c.id] for c in copies))
        for copy in copies:
            primary_name_by_id[copy.id] = name
        if days_union:
            symptom_breakdown.append(
                {
                    "activity_id": primary.id,
                    "activity": name,
                    "days": len(days_union),
                    "is_migraine": _is_migraine_name(name),
                }
            )
    symptom_breakdown.sort(key=lambda item: (-item["days"], item["activity"].lower()))

    position_breakdown = [
        {"position": pos, "days": len(days)}
        for pos, days in position_days.items()
        if days
    ]
    position_breakdown.sort(key=lambda item: (-item["days"], item["position"].lower()))

    daily_timeline: list[dict] = []
    for offset in range(total_days):
        day = start_date + dt.timedelta(days=offset)
        names = sorted({primary_name_by_id[aid] for aid in day_raw_activities.get(day, ()) if aid in primary_name_by_id})
        if day not in symptom_days:
            status = "clear"
        elif any(_is_migraine_name(n) for n in names):
            status = "migraine"
        else:
            status = "headache"
        daily_timeline.append(
            {
                "date": day.isoformat(),
                "status": status,
                "symptoms": names,
                "positions": sorted(day_positions.get(day, ())),
                "has_acupuncture": day in session_set,
                "confirmed": day in checks,
                "onset": checks[day].onset if day in checks else None,
            }
        )

    num_symptom_days = len(symptom_days)
    avg_severity = round(statistics.fmean(symptom_severities), 1) if symptom_severities else None
    previous_period = _resolve_prior_period(db, start_date, end_date, session_dates)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_days": total_days,
        "symptom_days": num_symptom_days,
        "clean_days": total_days - num_symptom_days,
        "frequency": round((num_symptom_days / total_days) * 100) if total_days > 0 else 0,
        "average_severity": avg_severity,
        "previous_period": previous_period,
        "symptom_breakdown": symptom_breakdown,
        "position_breakdown": position_breakdown,
        "daily_timeline": daily_timeline,
        "confirmed_days": len(checks),
    }


def _resolve_trigger_window(
    db: Session,
    window: str,
    start_date: dt.date | None,
    end_date: dt.date | None,
) -> tuple[dt.date | None, dt.date | None]:
    if window not in TRIGGER_WINDOWS:
        raise ValueError(f"window must be one of {TRIGGER_WINDOWS}")
    today = dt.datetime.now(UK_TZ).date()
    if window == "period":
        resolved_end = end_date or today
        resolved_start = start_date or (resolved_end - dt.timedelta(days=29))
        _check_report_range(resolved_start, resolved_end)
        return resolved_start, resolved_end
    if window == "90d":
        return today - dt.timedelta(days=89), today
    # window == "all"
    earliest = db.query(models.Mood.timestamp).order_by(models.Mood.timestamp.asc()).first()
    if earliest is None:
        return None, None
    earliest_date = earliest[0].astimezone(UK_TZ).date()
    resolved_end = max(today, earliest_date)
    return earliest_date, resolved_end


def _collect_explicit_left_out(db: Session) -> dict[int, dict]:
    left_out_dict: dict[int, dict] = {}
    explicit_left_out = (
        db.query(models.Activity)
        .filter(
            models.Activity.deprecated_at.is_(None),
            (models.Activity.report_role.in_(["habit", "describes_night", "reaction"]))
            | (models.Activity.hidden_pages.isnot(None)),
        )
        .all()
    )
    for act in explicit_left_out:
        name = (act.name or "").strip()
        if is_hidden_on(act, ACUPUNCTURE_PAGE):
            left_out_dict[act.id] = {"activity_id": act.id, "activity": name, "reason": "hidden"}
        elif act.report_role in ("habit", "describes_night", "reaction"):
            left_out_dict[act.id] = {"activity_id": act.id, "activity": name, "reason": act.report_role}
    return left_out_dict


USUAL_LOOKBACK_NIGHTS = 14
USUAL_MIN_NIGHTS = 5


def _minutes_of_day(moment: dt.datetime, evening_wraps: bool) -> int:
    local = moment.astimezone(UK_TZ)
    minutes = local.hour * 60 + local.minute
    # Bedtimes after midnight count as "late", not as early the same day.
    if evening_wraps and minutes < 12 * 60:
        minutes += 24 * 60
    return minutes


def _difference_from_usual(times_by_day: dict[dt.date, int], start: dt.date, end: dt.date) -> dict[dt.date, float]:
    """How many minutes each night's time was from the median of the nights before it."""
    result: dict[dt.date, float] = {}
    ordered = sorted(times_by_day)
    for day in ordered:
        if not (start <= day <= end):
            continue
        earlier = [
            times_by_day[d]
            for d in ordered
            if day - dt.timedelta(days=USUAL_LOOKBACK_NIGHTS) <= d < day
        ]
        if len(earlier) < USUAL_MIN_NIGHTS:
            continue
        result[day] = float(abs(times_by_day[day] - statistics.median(earlier)))
    return result


def _sleep_timing_inputs(db: Session, start: dt.date, end: dt.date) -> list[tuple[dict, str, bool | None, str]]:
    rows = (
        db.query(
            models.GarminSleepDaily.sleep_date,
            models.GarminSleepDaily.total_sleep_minutes,
            models.GarminSleepDaily.sleep_start,
            models.GarminSleepDaily.sleep_end,
        )
        .filter(
            models.GarminSleepDaily.sleep_date >= start - dt.timedelta(days=USUAL_LOOKBACK_NIGHTS + 1),
            models.GarminSleepDaily.sleep_date <= end,
        )
        .all()
    )
    length_map: dict[dt.date, float] = {}
    bedtimes: dict[dt.date, int] = {}
    waketimes: dict[dt.date, int] = {}
    for day, total_minutes, sleep_start, sleep_end in rows:
        if start <= day <= end and total_minutes:
            length_map[day] = round(total_minutes / 60, 2)
        if sleep_start is not None:
            bedtimes[day] = _minutes_of_day(sleep_start, evening_wraps=True)
        if sleep_end is not None:
            waketimes[day] = _minutes_of_day(sleep_end, evening_wraps=False)
    return [
        (length_map, "Sleep length (night before)", True, "h"),
        (_difference_from_usual(bedtimes, start, end), "Bedtime away from your usual (night before)", False, "min"),
        (_difference_from_usual(waketimes, start, end), "Wake-up time away from your usual", False, "min"),
    ]


def _body_battery_input(db: Session, start: dt.date, end: dt.date) -> tuple[dict, str, bool, str]:
    values: dict[dt.date, float] = {}
    battery_rows = (
        db.query(models.GarminBodyBatteryDaily.battery_date, models.GarminBodyBatteryDaily.morning_value)
        .filter(models.GarminBodyBatteryDaily.battery_date >= start, models.GarminBodyBatteryDaily.battery_date <= end)
        .all()
    )
    for day, value in battery_rows:
        if value is not None:
            values[day] = float(value)
    # The sleep record's wake-up reading is the more precise one when present.
    sleep_rows = (
        db.query(models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.body_battery_wakeup)
        .filter(models.GarminSleepDaily.sleep_date >= start, models.GarminSleepDaily.sleep_date <= end)
        .all()
    )
    for day, value in sleep_rows:
        if value is not None:
            values[day] = float(value)
    return (values, "Body Battery on waking", True, "")


def _weather_inputs(db: Session, start: dt.date, end: dt.date) -> list[tuple[dict, str, bool | None, str]]:
    rows = (
        db.query(
            models.WeatherDaily.weather_date,
            models.WeatherDaily.pressure_msl_mean,
            models.WeatherDaily.temperature_max_c,
        )
        .filter(models.WeatherDaily.weather_date >= start - dt.timedelta(days=1), models.WeatherDaily.weather_date <= end)
        .all()
    )
    pressure = {d: float(p) for d, p, _ in rows if p is not None}
    pressure_change = {
        d: round(p - pressure[d - dt.timedelta(days=1)], 1)
        for d, p in pressure.items()
        if start <= d <= end and (d - dt.timedelta(days=1)) in pressure
    }
    temp_max = {d: float(t) for d, _, t in rows if t is not None and start <= d <= end}
    return [
        # A falling pressure shows as a negative change, so "higher is better" here.
        (pressure_change, "Air pressure change since yesterday", True, "hPa"),
        (temp_max, "Highest temperature that day", None, "°C"),
    ]


def compute_headache_triggers(
    db: Session,
    window: str = "90d",
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> dict:
    resolved_start, resolved_end = _resolve_trigger_window(db, window, start_date, end_date)
    left_out_dict = _collect_explicit_left_out(db)

    if resolved_start is None or resolved_end is None:
        return {
            "window": window,
            "start_date": None,
            "end_date": None,
            "logged_days": 0,
            "confirmed_days": 0,
            "symptom_days": 0,
            "clean_days": 0,
            "tested_count": 0,
            "clue_count": 0,
            "verdict_kind": "insufficient_data",
            "triggers_day_before": [],
            "triggers_same_day": [],
            "biometrics": [],
            "no_clear_link": [],
            "too_early": [],
            "left_out": sorted(left_out_dict.values(), key=lambda x: x["activity"]),
            "min_nights": MIN_NIGHTS,
        }

    in_window = lambda d: resolved_start <= d <= resolved_end  # noqa: E731

    mood_from = dt.datetime.combine(resolved_start - dt.timedelta(days=2), dt.time(), tzinfo=UK_TZ)
    mood_to = dt.datetime.combine(resolved_end + dt.timedelta(days=1), dt.time(), tzinfo=UK_TZ)
    moods = (
        db.query(models.Mood)
        .options(selectinload(models.Mood.activities).selectinload(models.Activity.category))
        .filter(models.Mood.timestamp >= mood_from, models.Mood.timestamp < mood_to)
        .all()
    )

    checks = _load_headache_checks(db, resolved_start, resolved_end)

    active_logged_days: set[dt.date] = set()
    exposure_logged_days: set[dt.date] = set()
    before_sleep_target_days: set[dt.date] = set()
    symptom_days: set[dt.date] = set()

    day_before_item_days: dict[int, set[dt.date]] = defaultdict(set)
    same_day_item_days: dict[int, set[dt.date]] = defaultdict(set)
    all_activities: dict[int, models.Activity] = {}

    for mood in moods:
        mood_date = mood.timestamp.astimezone(UK_TZ).date()
        exposure_logged_days.add(mood_date)
        if in_window(mood_date):
            active_logged_days.add(mood_date)

        has_symptom_on_mood = False
        for activity in mood.activities:
            all_activities[activity.id] = activity
            if is_symptom(activity):
                has_symptom_on_mood = True
                continue

            category_name = activity.category.name if activity.category else None
            if is_before_sleep(category_name):
                day_affected = night_for_entry(mood.timestamp, True)
                if in_window(day_affected):
                    day_before_item_days[activity.id].add(day_affected)
                    before_sleep_target_days.add(day_affected)
                # Before Sleep items never count as same-day triggers
                continue

            day_affected = mood_date + dt.timedelta(days=1)
            if in_window(day_affected):
                day_before_item_days[activity.id].add(day_affected)
            if in_window(mood_date) and not _logged_after_onset(mood.timestamp, checks.get(mood_date)):
                same_day_item_days[activity.id].add(mood_date)

        if has_symptom_on_mood and in_window(mood_date):
            symptom_days.add(mood_date)

    # A day with a yes/no answer counts as logged, and the answer decides what kind of day it was.
    active_logged_days |= set(checks)
    symptom_days = _apply_checks(symptom_days, checks)
    clean_days = active_logged_days - symptom_days
    # Only days with entries tell us what was (or wasn't) done that day.
    same_day_eligible_days = active_logged_days & exposure_logged_days
    day_before_eligible_days = {
        d
        for d in active_logged_days
        if (d - dt.timedelta(days=1)) in exposure_logged_days or d in before_sleep_target_days
    }

    groups = _group_old_and_current_copies(db, all_activities)
    candidates_day_before: list[tuple[int | None, str, set[dt.date], set[dt.date], str]] = []
    candidates_same_day: list[tuple[int | None, str, set[dt.date], set[dt.date], str]] = []

    for primary, copies in groups:
        name = (primary.name or "").strip()
        if is_hidden_on(primary, ACUPUNCTURE_PAGE):
            left_out_dict[primary.id] = {"activity_id": primary.id, "activity": name, "reason": "hidden"}
            continue
        role = effective_role(primary)
        if role in ("habit", "describes_night", "reaction"):
            if role_was_set_by_owner(primary):
                left_out_dict[primary.id] = {"activity_id": primary.id, "activity": name, "reason": role}
            continue
        if role == "symptom":
            continue

        # Only possible_cause reaches here
        with_db = set().union(*(day_before_item_days[a.id] for a in copies)) & active_logged_days
        if with_db:
            without_db = day_before_eligible_days - with_db
            candidates_day_before.append((primary.id, name, with_db, without_db, "activity"))

        with_sd = set().union(*(same_day_item_days[a.id] for a in copies)) & active_logged_days
        if with_sd:
            without_sd = same_day_eligible_days - with_sd
            candidates_same_day.append((primary.id, name, with_sd, without_sd, "activity"))

    # Garmin Workouts (day before)
    workout_rows = (
        db.query(
            models.GarminActivity.start_time,
            models.GarminActivity.activity_date,
            models.GarminActivity.duration_seconds,
        )
        .filter(
            models.GarminActivity.activity_date >= resolved_start - dt.timedelta(days=2),
            models.GarminActivity.activity_date <= resolved_end,
        )
        .all()
    )

    workout_days: set[dt.date] = set()
    late_workout_days: set[dt.date] = set()
    long_workout_days: set[dt.date] = set()

    for start_time, act_date, duration in workout_rows:
        day_affected = night_for_workout(start_time) if start_time is not None else act_date + dt.timedelta(days=1)
        if in_window(day_affected) and day_affected in active_logged_days:
            workout_days.add(day_affected)
            if start_time and is_late_workout(start_time):
                late_workout_days.add(day_affected)
            if duration and duration >= 2700:
                long_workout_days.add(day_affected)

    earliest_workout = (
        db.query(models.GarminActivity.start_time, models.GarminActivity.activity_date)
        .order_by(models.GarminActivity.activity_date.asc(), models.GarminActivity.start_time.asc())
        .first()
    )
    if earliest_workout is not None:
        ew_start, ew_date = earliest_workout
        earliest_tracked = night_for_workout(ew_start) if ew_start is not None else ew_date + dt.timedelta(days=1)
        eligible_workout_days = {d for d in active_logged_days if d >= earliest_tracked}
    else:
        eligible_workout_days = set()

    for label, w_days in (
        (WORKOUT_LABEL, workout_days),
        (LATE_WORKOUT_LABEL, late_workout_days),
        (LONG_WORKOUT_LABEL, long_workout_days),
    ):
        if w_days:
            candidates_day_before.append((None, label, w_days, eligible_workout_days - w_days, "garmin"))

    raw_too_early: list[dict] = []
    evaluated_activity_ids: set[int] = set()

    def evaluate_candidates(candidate_list, timing: str) -> tuple[list[dict], list[dict]]:
        tested = []
        for activity_id, name, with_set, without_set, source in candidate_list:
            with_days = sorted(d for d in with_set if d in active_logged_days)
            without_days = sorted(d for d in without_set if d in active_logged_days)
            if not with_days:
                continue
            if not without_days:
                if len(with_days) < MIN_NIGHTS:
                    raw_too_early.append(
                        {"activity_id": activity_id, "activity": name, "with_nights": len(with_days), "source": source}
                    )
                continue

            with_vals = [1.0 if d in symptom_days else 0.0 for d in with_days]
            without_vals = [1.0 if d in symptom_days else 0.0 for d in without_days]
            result = compare(with_vals, without_vals)
            if result.confidence == "too_early":
                raw_too_early.append(
                    {"activity_id": activity_id, "activity": name, "with_nights": result.with_n, "source": source}
                )
                continue
            if activity_id is not None:
                evaluated_activity_ids.add(activity_id)
            tested.append((activity_id, name, with_days, with_vals + without_vals, result, source))

        if not tested:
            return [], []

        adjusted = bh_adjust([result.p_value for *_, result, _ in tested])
        all_items: list[dict] = []
        for (activity_id, name, with_days, pooled_vals, result, source), q_value in zip(tested, adjusted):
            confidence = level_for(q_value, result.with_n, result.without_n)
            effect_pct = round(result.effect * 100)
            negligible = abs(effect_pct) < MIN_BINARY_EFFECT_PCT or is_negligible(result.effect, pooled_vals)
            all_items.append(
                {
                    "activity_id": activity_id,
                    "activity": name,
                    "effect": effect_pct,
                    "with_nights": result.with_n,
                    "without_nights": result.without_n,
                    "confidence": confidence,
                    "better": effect_pct < 0,
                    "source": source,
                    "kind": "garmin_workout" if source == "garmin" else "activity",
                    "timing": timing,
                    "logged_with": [],
                    "_days": frozenset(with_days),
                    "_is_clue": confidence in ("strong", "some") and not negligible,
                }
            )

        # Twin detection across all tested items in this bucket
        by_days: dict[frozenset, list[str]] = defaultdict(list)
        for item in all_items:
            by_days[item["_days"]].append(item["activity"])
        clues: list[dict] = []
        weak_items: list[dict] = []
        for item in all_items:
            twins = by_days[item.pop("_days")]
            item["logged_with"] = sorted(n for n in twins if n != item["activity"])
            is_clue = item.pop("_is_clue")
            if is_clue:
                clues.append(item)
            else:
                weak_items.append(item)

        clues.sort(key=lambda x: (CONFIDENCE_ORDER[x["confidence"]], -abs(x["effect"])))
        weak_items.sort(key=lambda x: (CONFIDENCE_ORDER[x["confidence"]], -abs(x["effect"])))
        return clues, weak_items

    triggers_day_before, weak_day_before = evaluate_candidates(candidates_day_before, "day_before")
    triggers_same_day, weak_same_day = evaluate_candidates(candidates_same_day, "same_day")

    # Garmin Biometrics Analysis (BH-adjusted + negligible filtered)
    bio_inputs: list[tuple[dict[dt.date, float], str, bool, str]] = []

    # 1. Sleep score (night leading into d)
    sleep_rows = (
        db.query(models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.sleep_score)
        .filter(
            models.GarminSleepDaily.sleep_date >= resolved_start,
            models.GarminSleepDaily.sleep_date <= resolved_end,
        )
        .all()
    )
    bio_inputs.append(
        ({d: float(v) for d, v in sleep_rows if v is not None}, "Sleep Score (night before)", True, "pts")
    )

    # 2. Overnight Stress (with accurately shifted & relabelled Daytime Stress fallback)
    stress_sleep_rows = (
        db.query(models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.payload)
        .filter(
            models.GarminSleepDaily.sleep_date >= resolved_start,
            models.GarminSleepDaily.sleep_date <= resolved_end,
        )
        .all()
    )
    sleep_stress_map = {
        d: val
        for d, p in stress_sleep_rows
        if (val := _dig(p, ("dailySleepDTO", "avgSleepStress"))) is not None
    }
    if sleep_stress_map and len(sleep_stress_map) * 2 >= len(stress_sleep_rows):
        bio_inputs.append((sleep_stress_map, "Overnight Stress (night before)", False, ""))
    else:
        stress_daily_rows = (
            db.query(models.GarminStressDaily.stress_date, models.GarminStressDaily.overall_stress_level)
            .filter(
                models.GarminStressDaily.stress_date >= resolved_start - dt.timedelta(days=1),
                models.GarminStressDaily.stress_date <= resolved_end,
            )
            .all()
        )
        daytime_stress_map = {d + dt.timedelta(days=1): float(v) for d, v in stress_daily_rows if v is not None}
        bio_inputs.append((daytime_stress_map, "Daytime Stress (day before)", False, ""))

    # 3. Overnight HRV (full 8 JSON lookup paths matching lifestyle_impact.py)
    hrv_rows = (
        db.query(models.GarminHRVDaily.hrv_date, models.GarminHRVDaily.payload)
        .filter(
            models.GarminHRVDaily.hrv_date >= resolved_start,
            models.GarminHRVDaily.hrv_date <= resolved_end,
        )
        .all()
    )
    hrv_map = {}
    for d, p in hrv_rows:
        val = _dig(
            p,
            ("hrvSummary", "lastNightAvg"),
            ("hrvSummary", "lastNightAverage"),
            ("hrvSummary", "lastNight"),
            ("hrvStatus", "lastNightAvg"),
            ("hrvStatus", "lastNightAverage"),
            ("hrvStatus", "lastNight"),
            ("lastNightAvg",),
            ("lastNightAverage",),
        )
        if val is not None:
            hrv_map[d] = val
    bio_inputs.append((hrv_map, "Overnight HRV (night before)", True, "ms"))

    # 4. Resting Heart Rate (day before)
    rhr_rows = (
        db.query(
            models.GarminRestingHeartRateDaily.heart_rate_date,
            models.GarminRestingHeartRateDaily.resting_heart_rate,
        )
        .filter(
            models.GarminRestingHeartRateDaily.heart_rate_date >= resolved_start - dt.timedelta(days=1),
            models.GarminRestingHeartRateDaily.heart_rate_date <= resolved_end,
        )
        .all()
    )
    rhr_map = {d + dt.timedelta(days=1): float(v) for d, v in rhr_rows if v is not None}
    bio_inputs.append((rhr_map, "Resting Heart Rate (day before)", False, "bpm"))

    # 5. Hydration (% of goal, day before). 0 ml or missing means unknown!
    hydration_rows = (
        db.query(
            models.GarminHydrationDaily.hydration_date,
            models.GarminHydrationDaily.consumed_ml,
            models.GarminHydrationDaily.goal_ml,
        )
        .filter(
            models.GarminHydrationDaily.hydration_date >= resolved_start - dt.timedelta(days=1),
            models.GarminHydrationDaily.hydration_date <= resolved_end,
        )
        .all()
    )
    hydration_map = {}
    for h_date, consumed, goal in hydration_rows:
        if consumed is not None and consumed > 0 and goal is not None and goal > 0:
            hydration_map[h_date + dt.timedelta(days=1)] = round((consumed / goal) * 100, 1)
    bio_inputs.append((hydration_map, "Hydration % of goal (day before)", True, "%"))

    bio_inputs.extend(_sleep_timing_inputs(db, resolved_start, resolved_end))
    bio_inputs.append(_body_battery_input(db, resolved_start, resolved_end))
    weather_inputs = _weather_inputs(db, resolved_start, resolved_end)
    bio_inputs.extend(weather_inputs)
    weather_labels = {label for _, label, _, _ in weather_inputs}

    tested_bios = []
    for metric_map, label, higher_is_better, unit in bio_inputs:
        symp_vals = [metric_map[d] for d in symptom_days if d in metric_map]
        clean_vals = [metric_map[d] for d in clean_days if d in metric_map]
        if not symp_vals and not clean_vals:
            continue
        if not symp_vals or not clean_vals:
            raw_too_early.append(
                {
                    "activity_id": None,
                    "activity": label,
                    "with_nights": min(len(symp_vals), len(clean_vals)),
                    "source": "weather" if label in weather_labels else "garmin",
                }
            )
            continue
        res = compare(symp_vals, clean_vals)
        if res.confidence == "too_early":
            raw_too_early.append(
                {
                    "activity_id": None,
                    "activity": label,
                    "with_nights": min(res.with_n, res.without_n),
                    "source": "weather" if label in weather_labels else "garmin",
                }
            )
            continue
        tested_bios.append((label, higher_is_better, unit, symp_vals + clean_vals, res))

    biometrics: list[dict] = []
    weak_biometrics: list[dict] = []
    if tested_bios:
        bio_adjusted = bh_adjust([res.p_value for *_, res in tested_bios])
        for (label, higher_is_better, unit, pooled_vals, res), q_value in zip(tested_bios, bio_adjusted):
            confidence = level_for(q_value, res.with_n, res.without_n)
            symp_avg = round(res.with_mean, 1)
            clean_avg = round(res.without_mean, 1)
            diff = round(symp_avg - clean_avg, 1)
            negligible = diff == 0.0 or is_negligible(res.effect, pooled_vals)
            entry = {
                "kind": "biometric",
                "timing": "biometric",
                "source": "weather" if label in weather_labels else "garmin",
                "metric": label,
                "symptom_avg": symp_avg,
                "clean_avg": clean_avg,
                "effect": diff,
                "unit": unit,
                "with_nights": res.with_n,
                "without_nights": res.without_n,
                "confidence": confidence,
                # Neutral measures (e.g. temperature) have no "better" direction.
                "better": (diff > 0) == higher_is_better if diff != 0.0 and higher_is_better is not None else False,
            }
            if confidence in ("strong", "some") and not negligible:
                biometrics.append(entry)
            else:
                weak_biometrics.append(entry)

    biometrics.sort(key=lambda x: (CONFIDENCE_ORDER[x["confidence"]], -abs(x["effect"])))
    weak_biometrics.sort(key=lambda x: (CONFIDENCE_ORDER[x["confidence"]], -abs(x["effect"])))

    # Cross-bucket deduplication for no_clear_link
    clue_activity_ids = {
        item["activity_id"]
        for item in triggers_day_before + triggers_same_day
        if item["activity_id"] is not None
    }
    clue_garmin_labels = {
        item["activity"]
        for item in triggers_day_before + triggers_same_day
        if item["activity_id"] is None
    }

    no_clear_link: list[dict] = []
    seen_weak_activities: set[int] = set()
    for item in weak_day_before + weak_same_day:
        aid = item["activity_id"]
        if aid is not None:
            if aid in clue_activity_ids or aid in seen_weak_activities:
                continue
            seen_weak_activities.add(aid)
        else:
            if item["activity"] in clue_garmin_labels:
                continue
        no_clear_link.append(item)
    no_clear_link.extend(weak_biometrics)

    # Deduplicate too_early (suppressing anything already evaluated in day_before or same_day)
    too_early_by_key: dict[tuple[int | None, str], dict] = {}
    for item in raw_too_early:
        aid = item["activity_id"]
        if aid is not None and aid in evaluated_activity_ids:
            continue
        key = (aid, item["activity"])
        prev = too_early_by_key.get(key)
        if prev is None or item["with_nights"] > prev["with_nights"]:
            too_early_by_key[key] = item
    too_early = sorted(too_early_by_key.values(), key=lambda x: (-x["with_nights"], x["activity"]))
    left_out = sorted(left_out_dict.values(), key=lambda x: x["activity"])

    clue_count = len(triggers_day_before) + len(triggers_same_day) + len(biometrics)
    tested_count = clue_count + len(no_clear_link)
    if clue_count > 0:
        verdict_kind = "clues_found"
    elif tested_count > 0 and len(symptom_days) >= MIN_NIGHTS and len(clean_days) >= MIN_NIGHTS:
        verdict_kind = "looks_random"
    else:
        verdict_kind = "insufficient_data"

    return {
        "window": window,
        "start_date": resolved_start.isoformat(),
        "end_date": resolved_end.isoformat(),
        "logged_days": len(active_logged_days),
        "confirmed_days": len(checks),
        "symptom_days": len(symptom_days),
        "clean_days": len(clean_days),
        "tested_count": tested_count,
        "clue_count": clue_count,
        "verdict_kind": verdict_kind,
        "triggers_day_before": triggers_day_before,
        "triggers_same_day": triggers_same_day,
        "biometrics": biometrics,
        "no_clear_link": no_clear_link,
        "too_early": too_early,
        "left_out": left_out,
        "min_nights": MIN_NIGHTS,
    }


def compute_headache_summary(
    db: Session,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> dict:
    """Backwards-compatible combined headache summary over [start_date, end_date]."""
    appointment = compute_appointment_summary(db, start_date=start_date, end_date=end_date)
    triggers = compute_headache_triggers(db, window="period", start_date=start_date, end_date=end_date)
    return {
        **appointment,
        "logged_days": triggers["logged_days"],
        "confirmed_days": triggers["confirmed_days"],
        "tested_count": triggers["tested_count"],
        "clue_count": triggers["clue_count"],
        "verdict_kind": triggers["verdict_kind"],
        "triggers_day_before": triggers["triggers_day_before"],
        "triggers_same_day": triggers["triggers_same_day"],
        "biometrics": triggers["biometrics"],
        "no_clear_link": triggers["no_clear_link"],
        "too_early": triggers["too_early"],
        "left_out": triggers["left_out"],
        "min_nights": triggers["min_nights"],
    }

