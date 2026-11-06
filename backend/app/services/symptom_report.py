import datetime as dt
import math
import statistics
from collections import defaultdict

from sqlalchemy.orm import Session, selectinload

from .. import models
from .comparison import CONFIDENCE_ORDER, MIN_NIGHTS, bh_adjust, compare, level_for
from .insight_dates import UK_TZ, is_late_workout, night_for_entry
from .item_roles import (
    ACUPUNCTURE_PAGE,
    effective_role,
    is_before_sleep,
    is_hidden_on,
    is_symptom,
    role_was_set_by_owner,
)

WORKOUT_LABEL = "Workout (day before)"
LATE_WORKOUT_LABEL = "Late workout (after 6pm, day before)"
LONG_WORKOUT_LABEL = "Long workout (> 45m, day before)"


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


def _group_old_and_current_copies(
    db: Session, logged: dict[int, models.Activity]
) -> list[tuple[models.Activity, list[models.Activity]]]:
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


def compute_headache_summary(
    db: Session,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> dict:
    today = dt.datetime.now(UK_TZ).date()
    end_date = end_date or today
    start_date = start_date or (end_date - dt.timedelta(days=29))

    in_window = lambda d: start_date <= d <= end_date  # noqa: E731
    total_days = max(1, (end_date - start_date).days + 1)
    all_window_days = {start_date + dt.timedelta(days=i) for i in range(total_days)}

    # Fetch moods covering the window and the 2 days prior (for day-before activity lookups)
    mood_from = dt.datetime.combine(start_date - dt.timedelta(days=2), dt.time(), tzinfo=UK_TZ)
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

    symptom_days = set()
    symptom_severities: list[float] = []

    day_before_item_days: dict[int, set[dt.date]] = defaultdict(set)
    same_day_item_days: dict[int, set[dt.date]] = defaultdict(set)
    all_activities: dict[int, models.Activity] = {}

    for mood in moods:
        mood_date = mood.timestamp.astimezone(UK_TZ).date()
        has_symptom_on_mood = False

        for activity in mood.activities:
            all_activities[activity.id] = activity
            if is_symptom(activity):
                has_symptom_on_mood = True
                for det in mood.activity_details:
                    if det.activity_id == activity.id and det.severity is not None:
                        symptom_severities.append(float(det.severity))
            else:
                category_name = activity.category.name if activity.category else None
                # Day & night before matching:
                # Before sleep items belong to wake morning (day affected).
                # Daytime items logged on d-1 affect d.
                if is_before_sleep(category_name):
                    day_affected = night_for_entry(mood.timestamp, True)
                else:
                    day_affected = mood_date + dt.timedelta(days=1)

                if in_window(day_affected):
                    day_before_item_days[activity.id].add(day_affected)

                if in_window(mood_date):
                    same_day_item_days[activity.id].add(mood_date)

        if has_symptom_on_mood and in_window(mood_date):
            symptom_days.add(mood_date)

    num_symptom_days = len(symptom_days)
    clean_days = all_window_days - symptom_days
    num_clean_days = len(clean_days)
    avg_severity = round(statistics.fmean(symptom_severities), 1) if symptom_severities else None

    # Candidate grouping
    groups = _group_old_and_current_copies(db, all_activities)
    left_out_dict: dict[int, dict] = {}
    too_early: list[dict] = []

    # Include any explicitly hidden or habit/describes_night activities across database so user can restore them
    explicit_left_out = (
        db.query(models.Activity)
        .filter(
            models.Activity.deprecated_at.is_(None),
            (models.Activity.report_role.in_(["habit", "describes_night"])) | (models.Activity.hidden_pages.isnot(None)),
        )
        .all()
    )
    for act in explicit_left_out:
        name = (act.name or "").strip()
        if is_hidden_on(act, ACUPUNCTURE_PAGE):
            left_out_dict[act.id] = {"activity_id": act.id, "activity": name, "reason": "hidden"}
        elif act.report_role in ("habit", "describes_night"):
            left_out_dict[act.id] = {"activity_id": act.id, "activity": name, "reason": act.report_role}

    candidates_day_before: list[tuple[int | None, str, set[dt.date], set[dt.date], str]] = []
    candidates_same_day: list[tuple[int | None, str, set[dt.date], set[dt.date], str]] = []

    for primary, copies in groups:
        name = (primary.name or "").strip()
        if is_hidden_on(primary, ACUPUNCTURE_PAGE):
            left_out_dict[primary.id] = {"activity_id": primary.id, "activity": name, "reason": "hidden"}
            continue
        role = effective_role(primary)
        if role == "habit":
            if role_was_set_by_owner(primary):
                left_out_dict[primary.id] = {"activity_id": primary.id, "activity": name, "reason": "habit"}
            continue
        if role == "describes_night":
            if role_was_set_by_owner(primary):
                left_out_dict[primary.id] = {"activity_id": primary.id, "activity": name, "reason": "describes_night"}
            continue
        if role == "symptom":
            continue

        # Day before candidates (only possible_cause)
        if role == "possible_cause":
            with_set = set().union(*(day_before_item_days[a.id] for a in copies))
            candidates_day_before.append((primary.id, name, with_set, all_window_days - with_set, "activity"))

        # Same day candidates (possible_cause or reaction)
        if role in ("possible_cause", "reaction"):
            with_set_same = set().union(*(same_day_item_days[a.id] for a in copies))
            candidates_same_day.append((primary.id, name, with_set_same, all_window_days - with_set_same, "activity"))

    # Garmin Workouts (day before)
    workout_rows = (
        db.query(models.GarminActivity.start_time, models.GarminActivity.activity_date, models.GarminActivity.duration_seconds)
        .filter(
            models.GarminActivity.activity_date >= start_date - dt.timedelta(days=2),
            models.GarminActivity.activity_date <= end_date,
        )
        .all()
    )

    workout_days = set()
    late_workout_days = set()
    long_workout_days = set()

    for start_time, act_date, duration in workout_rows:
        day_affected = act_date + dt.timedelta(days=1)
        if in_window(day_affected):
            workout_days.add(day_affected)
            if start_time and is_late_workout(start_time):
                late_workout_days.add(day_affected)
            if duration and duration >= 2700:
                long_workout_days.add(day_affected)

    earliest_workout = (
        db.query(models.GarminActivity.activity_date)
        .order_by(models.GarminActivity.activity_date.asc())
        .first()
    )
    if earliest_workout is not None:
        eligible_workout_days = {d for d in all_window_days if d >= earliest_workout[0] + dt.timedelta(days=1)}
    else:
        eligible_workout_days = set()

    for label, w_days in (
        (WORKOUT_LABEL, workout_days),
        (LATE_WORKOUT_LABEL, late_workout_days),
        (LONG_WORKOUT_LABEL, long_workout_days),
    ):
        if w_days:
            candidates_day_before.append((None, label, w_days, eligible_workout_days - w_days, "garmin"))

    def evaluate_candidates(candidate_list):
        tested = []
        for activity_id, name, with_set, without_set, source in candidate_list:
            with_days = sorted(d for d in with_set if d in all_window_days)
            without_days = sorted(d for d in without_set if d in all_window_days)
            if not with_days or not without_days:
                continue

            with_vals = [1.0 if d in symptom_days else 0.0 for d in with_days]
            without_vals = [1.0 if d in symptom_days else 0.0 for d in without_days]

            result = compare(with_vals, without_vals)
            if result.confidence == "too_early":
                too_early.append({"activity_id": activity_id, "activity": name, "with_nights": result.with_n})
                continue
            tested.append((activity_id, name, with_days, without_days, result, source))

        if not tested:
            return []

        adjusted = bh_adjust([result.p_value for *_, result, _ in tested])
        items = []
        for (activity_id, name, with_days, without_days, result, source), q_value in zip(tested, adjusted):
            result.confidence = level_for(q_value, result.with_n, result.without_n)
            effect_pct = round(result.effect * 100)
            items.append(
                {
                    "activity_id": activity_id,
                    "activity": name,
                    "effect": effect_pct,
                    "with_nights": result.with_n,
                    "without_nights": result.without_n,
                    "confidence": result.confidence,
                    "better": effect_pct < 0,
                    "source": source,
                    "logged_with": [],
                    "_days": frozenset(with_days),
                }
            )

        # Twin detection
        by_days: dict[frozenset, list[str]] = defaultdict(list)
        for item in items:
            by_days[item["_days"]].append(item["activity"])
        for item in items:
            twins = by_days[item.pop("_days")]
            item["logged_with"] = sorted(n for n in twins if n != item["activity"])

        items.sort(key=lambda x: (CONFIDENCE_ORDER[x["confidence"]], -abs(x["effect"])))
        return items

    triggers_day_before = evaluate_candidates(candidates_day_before)
    triggers_same_day = evaluate_candidates(candidates_same_day)

    # Garmin Biometrics Analysis
    biometrics = []

    def evaluate_biometric(metric_map, label, higher_is_better, unit=""):
        symp_vals = [metric_map[d] for d in symptom_days if d in metric_map]
        clean_vals = [metric_map[d] for d in clean_days if d in metric_map]
        if not symp_vals or not clean_vals:
            return

        res = compare(symp_vals, clean_vals)
        if res.confidence == "too_early":
            return

        symp_avg = round(res.with_mean, 1)
        clean_avg = round(res.without_mean, 1)
        diff = round(symp_avg - clean_avg, 1)

        biometrics.append(
            {
                "metric": label,
                "symptom_avg": symp_avg,
                "clean_avg": clean_avg,
                "effect": diff,
                "unit": unit,
                "confidence": res.confidence,
                "better": (diff > 0) == higher_is_better,
            }
        )

    # 1. Sleep score (night leading into d)
    sleep_rows = db.query(models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.sleep_score).filter(
        models.GarminSleepDaily.sleep_date >= start_date, models.GarminSleepDaily.sleep_date <= end_date
    ).all()
    sleep_map = {d: float(v) for d, v in sleep_rows if v is not None}
    evaluate_biometric(sleep_map, "Sleep Score (night before)", higher_is_better=True, unit="pts")

    # 2. Overnight Stress
    stress_rows = db.query(models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.payload).filter(
        models.GarminSleepDaily.sleep_date >= start_date, models.GarminSleepDaily.sleep_date <= end_date
    ).all()
    stress_map = {}
    for d, p in stress_rows:
        val = _dig(p, ("dailySleepDTO", "avgSleepStress"))
        if val is not None:
            stress_map[d] = val
    if not stress_map:
        stress_daily_rows = db.query(models.GarminStressDaily.stress_date, models.GarminStressDaily.overall_stress_level).filter(
            models.GarminStressDaily.stress_date >= start_date, models.GarminStressDaily.stress_date <= end_date
        ).all()
        stress_map = {d: float(v) for d, v in stress_daily_rows if v is not None}
    evaluate_biometric(stress_map, "Overnight Stress (night before)", higher_is_better=False, unit="")

    # 3. Overnight HRV
    hrv_rows = db.query(models.GarminHRVDaily.hrv_date, models.GarminHRVDaily.payload).filter(
        models.GarminHRVDaily.hrv_date >= start_date, models.GarminHRVDaily.hrv_date <= end_date
    ).all()
    hrv_map = {}
    for d, p in hrv_rows:
        val = _dig(
            p,
            ("hrvSummary", "lastNightAvg"),
            ("hrvSummary", "lastNightAverage"),
            ("hrvStatus", "lastNightAvg"),
            ("hrvStatus", "lastNightAverage"),
        )
        if val is not None:
            hrv_map[d] = val
    evaluate_biometric(hrv_map, "Overnight HRV (night before)", higher_is_better=True, unit="ms")

    # 4. Resting Heart Rate (day before)
    rhr_rows = db.query(models.GarminRestingHeartRateDaily.heart_rate_date, models.GarminRestingHeartRateDaily.resting_heart_rate).filter(
        models.GarminRestingHeartRateDaily.heart_rate_date >= start_date - dt.timedelta(days=1),
        models.GarminRestingHeartRateDaily.heart_rate_date <= end_date,
    ).all()
    rhr_map = {d + dt.timedelta(days=1): float(v) for d, v in rhr_rows if v is not None}
    evaluate_biometric(rhr_map, "Resting Heart Rate (day before)", higher_is_better=False, unit="bpm")

    # 5. Hydration (% of goal, day before). CRITICAL: 0 ml or no record means unknown!
    hydration_rows = db.query(
        models.GarminHydrationDaily.hydration_date,
        models.GarminHydrationDaily.consumed_ml,
        models.GarminHydrationDaily.goal_ml,
    ).filter(
        models.GarminHydrationDaily.hydration_date >= start_date - dt.timedelta(days=1),
        models.GarminHydrationDaily.hydration_date <= end_date,
    ).all()
    hydration_map = {}
    for h_date, consumed, goal in hydration_rows:
        if consumed is not None and consumed > 0 and goal is not None and goal > 0:
            day_affected = h_date + dt.timedelta(days=1)
            hydration_map[day_affected] = round((consumed / goal) * 100, 1)
    evaluate_biometric(hydration_map, "Hydration % of goal (day before)", higher_is_better=True, unit="%")

    biometrics.sort(key=lambda x: (CONFIDENCE_ORDER[x["confidence"]], -abs(x["effect"])))
    too_early.sort(key=lambda x: (-x["with_nights"], x["activity"]))
    left_out = sorted(left_out_dict.values(), key=lambda x: x["activity"])

    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "total_days": total_days,
        "symptom_days": num_symptom_days,
        "clean_days": num_clean_days,
        "frequency": round((num_symptom_days / total_days) * 100) if total_days > 0 else 0,
        "average_severity": avg_severity,
        "triggers_day_before": triggers_day_before,
        "triggers_same_day": triggers_same_day,
        "biometrics": biometrics,
        "too_early": too_early,
        "left_out": left_out,
        "min_nights": MIN_NIGHTS,
    }
