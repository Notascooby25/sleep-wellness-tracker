import datetime as dt
import math
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..database import get_db
from ..services.comparison import CONFIDENCE_ORDER, MIN_NIGHTS, compare, is_negligible
from ..services.insight_dates import UK_TZ, is_late_workout, night_for_entry, night_for_workout
from ..services.item_roles import (
    LIFESTYLE_PAGE,
    effective_role,
    is_before_sleep,
    is_hidden_on,
    role_was_set_by_owner,
)

router = APIRouter(prefix="/lifestyle-impact", tags=["lifestyle-impact"])

ALLOWED_DAYS = (28, 84, 182)
WORKOUT_LABEL = "Workout"
LATE_WORKOUT_LABEL = "Late workout (after 6pm)"

_METRICS = {
    "sleep_score": {"label": "Sleep score", "higher_is_better": True},
    "overnight_hrv": {"label": "Overnight HRV", "higher_is_better": True},
    "overnight_stress": {"label": "Overnight stress", "higher_is_better": False},
    "resting_heart_rate": {"label": "Resting heart rate", "higher_is_better": False},
    "steps": {"label": "Steps", "higher_is_better": True},
}


def _format_period_label(start_date: dt.date, end_date: dt.date) -> str:
    return f"{start_date.day} {start_date.strftime('%b')} - {end_date.day} {end_date.strftime('%b')}"


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


def _rows(db: Session, date_col, value_col, start: dt.date, end: dt.date) -> dict[dt.date, float]:
    rows = db.query(date_col, value_col).filter(date_col >= start, date_col <= end).all()
    return {day: number for day, value in rows if (number := _number(value)) is not None}


def _metric_by_night(db: Session, metric: str, start: dt.date, end: dt.date) -> tuple[dict[dt.date, float], str]:
    label = _METRICS[metric]["label"]
    if metric == "sleep_score":
        return _rows(db, models.GarminSleepDaily.sleep_date, models.GarminSleepDaily.sleep_score, start, end), label
    if metric == "resting_heart_rate":
        model = models.GarminRestingHeartRateDaily
        return _rows(db, model.heart_rate_date, model.resting_heart_rate, start, end), label
    if metric == "steps":
        return _rows(db, models.GarminStepsDaily.steps_date, models.GarminStepsDaily.total_steps, start, end), label
    if metric == "overnight_hrv":
        model = models.GarminHRVDaily
        rows = db.query(model.hrv_date, model.payload).filter(model.hrv_date >= start, model.hrv_date <= end).all()
        values = {
            day: value
            for day, payload in rows
            if (value := _dig(payload, ("hrvSummary", "lastNightAvg"), ("hrvSummary", "lastNightAverage"), ("lastNightAvg",)))
            is not None
        }
        return values, label

    model = models.GarminSleepDaily
    rows = db.query(model.sleep_date, model.payload).filter(model.sleep_date >= start, model.sleep_date <= end).all()
    sleep_stress = {
        day: value for day, payload in rows if (value := _dig(payload, ("dailySleepDTO", "avgSleepStress"))) is not None
    }
    if sleep_stress and len(sleep_stress) * 2 >= len(rows):
        return sleep_stress, label
    stress = models.GarminStressDaily
    return _rows(db, stress.stress_date, stress.overall_stress_level, start, end), "Stress"


def _round_effect(effect: float, metric: str) -> float:
    return round(effect) if metric == "steps" else round(effect, 1)


def compute_lifestyle_impact(db: Session, metric: str, days: int, end_date: dt.date | None = None) -> dict:
    higher_is_better = _METRICS[metric]["higher_is_better"]
    end_date = end_date or _today()
    start_date = end_date - dt.timedelta(days=days - 1)
    values_by_night, metric_label = _metric_by_night(db, metric, start_date, end_date)
    window_values = list(values_by_night.values())

    in_window = lambda night: start_date <= night <= end_date  # noqa: E731

    mood_from = dt.datetime.combine(start_date - dt.timedelta(days=2), dt.time(), tzinfo=UK_TZ)
    mood_to = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time(), tzinfo=UK_TZ)
    moods = (
        db.query(models.Mood)
        .options(selectinload(models.Mood.activities).selectinload(models.Activity.category))
        .filter(models.Mood.timestamp >= mood_from, models.Mood.timestamp < mood_to)
        .all()
    )

    activities: dict[int, models.Activity] = {}
    item_nights: dict[int, set[dt.date]] = defaultdict(set)
    logged_categories: dict[dt.date, set] = defaultdict(set)
    for mood in moods:
        for activity in mood.activities:
            category_name = activity.category.name if activity.category is not None else None
            night = night_for_entry(mood.timestamp, is_before_sleep(category_name))
            if not in_window(night):
                continue
            activities[activity.id] = activity
            item_nights[activity.id].add(night)
            logged_categories[night].add(activity.category_id)

    candidates: list[tuple[int | None, str, set[dt.date], set[dt.date]]] = []
    left_out: list[dict] = []
    for activity_id, activity in activities.items():
        name = (activity.name or "").strip()
        if is_hidden_on(activity, LIFESTYLE_PAGE):
            left_out.append({"activity_id": activity_id, "activity": name, "reason": "hidden"})
            continue
        role = effective_role(activity)
        if role != "possible_cause":
            if role_was_set_by_owner(activity):
                left_out.append({"activity_id": activity_id, "activity": name, "reason": role})
            continue
        with_set = item_nights[activity_id]
        without_set = {
            night
            for night, categories in logged_categories.items()
            if activity.category_id in categories and night not in with_set
        }
        candidates.append((activity_id, name, with_set, without_set))

    workout_rows = (
        db.query(models.GarminActivity.start_time)
        .filter(
            models.GarminActivity.start_time.isnot(None),
            models.GarminActivity.activity_date >= start_date - dt.timedelta(days=2),
            models.GarminActivity.activity_date <= end_date,
        )
        .all()
    )
    workout_nights = {night_for_workout(start) for (start,) in workout_rows}
    late_nights = {night_for_workout(start) for (start,) in workout_rows if is_late_workout(start)}
    all_nights = set(values_by_night)
    for label, nights in ((WORKOUT_LABEL, workout_nights), (LATE_WORKOUT_LABEL, late_nights)):
        nights = {night for night in nights if in_window(night)}
        if nights:
            candidates.append((None, label, nights, all_nights - nights))

    items: list[dict] = []
    too_early: list[dict] = []
    for activity_id, name, with_set, without_set in candidates:
        with_nights = sorted(night for night in with_set if night in values_by_night)
        without_nights = sorted(night for night in without_set if night in values_by_night)
        if not with_nights:
            continue
        result = compare([values_by_night[n] for n in with_nights], [values_by_night[n] for n in without_nights])
        if result.confidence == "too_early":
            too_early.append({"activity_id": activity_id, "activity": name, "with_nights": result.with_n})
            continue
        if is_negligible(result.effect, window_values):
            continue
        items.append(
            {
                "activity_id": activity_id,
                "activity": name,
                "effect": _round_effect(result.effect, metric),
                "with_nights": result.with_n,
                "without_nights": result.without_n,
                "confidence": result.confidence,
                "better": (result.effect > 0) == higher_is_better,
                "logged_with": [],
                "_nights": frozenset(with_nights),
            }
        )

    by_nights: dict[frozenset, list[str]] = defaultdict(list)
    for item in items:
        by_nights[item["_nights"]].append(item["activity"])
    for item in items:
        twins = by_nights[item.pop("_nights")]
        item["logged_with"] = sorted(name for name in twins if name != item["activity"])

    items.sort(key=lambda item: (CONFIDENCE_ORDER[item["confidence"]], -abs(item["effect"])))
    too_early.sort(key=lambda item: (-item["with_nights"], item["activity"]))
    left_out.sort(key=lambda item: item["activity"])

    return {
        "metric": metric,
        "metric_label": metric_label,
        "higher_is_better": higher_is_better,
        "period_label": _format_period_label(start_date, end_date),
        "avg_value": round(statistics.fmean(window_values), 1) if window_values else None,
        "nights_analysed": len(window_values),
        "items": items,
        "too_early": too_early,
        "left_out": left_out,
        "min_nights": MIN_NIGHTS,
    }


@router.get("")
def get_lifestyle_impact(
    metric: str = Query(..., pattern="^(sleep_score|overnight_hrv|overnight_stress|resting_heart_rate|steps)$"),
    days: int = Query(28),
    end_date: dt.date | None = Query(None),
    db: Session = Depends(get_db),
):
    if days not in ALLOWED_DAYS:
        raise HTTPException(status_code=422, detail=f"days must be one of {ALLOWED_DAYS}")
    return compute_lifestyle_impact(db, metric, days, end_date)


def _today() -> dt.date:
    return dt.datetime.now(UK_TZ).date()


def _advice_from_item(score: int, item: dict) -> str:
    name, size = item["activity"], abs(item["effect"])
    if item["better"]:
        return (
            f"Your last sleep score was {score}. On nights after {name}, your sleep score has been "
            f"about {size:.0f} points higher. Worth making time for it tonight."
        )
    return (
        f"Your last sleep score was {score}. On nights after {name}, your sleep score has been "
        f"about {size:.0f} points lower. Worth skipping it tonight."
    )


@router.get("/advice")
def get_daily_advice(db: Session = Depends(get_db)):
    latest_sleep = db.query(models.GarminSleepDaily).order_by(models.GarminSleepDaily.sleep_date.desc()).first()
    impact = compute_lifestyle_impact(db, "sleep_score", 84, _today())
    evidence = [
        item for item in impact["items"] if item["confidence"] in ("strong", "some") and item["activity_id"] is not None
    ]

    advice_msg = "Keep logging your activities to receive personalized predictive advice!"
    if latest_sleep and latest_sleep.sleep_score is not None:
        score = latest_sleep.sleep_score
        if evidence:
            advice_msg = _advice_from_item(score, evidence[0])
        elif score < 75:
            advice_msg = f"Your last sleep score was {score}. Your body needs more rest. Try taking it easy and going to bed a bit earlier tonight."
        else:
            advice_msg = f"Great sleep score of {score}! You're primed for a highly productive day."

    return {"advice": advice_msg}
