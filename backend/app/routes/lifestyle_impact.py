import datetime as dt
import math
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..database import get_db

router = APIRouter(prefix="/lifestyle-impact", tags=["lifestyle-impact"])

_SLEEP_CATEGORY_TOKENS = ("lifestyle", "before sleep", "during sleep", "pre-sleep", "presleep")

_METRIC_CONFIG = {
    "sleep_score": {
        "model": models.GarminSleepDaily,
        "date_field": models.GarminSleepDaily.sleep_date,
        "value_field": models.GarminSleepDaily.sleep_score,
        "higher_is_better": True,
        "label": "sleep score",
    },
    "overnight_hrv": {
        "model": models.GarminHRVDaily,
        "date_field": models.GarminHRVDaily.hrv_date,
        "value_field": models.GarminHRVDaily.weekly_avg,
        "higher_is_better": True,
        "label": "overnight HRV",
    },
    "overnight_stress": {
        "model": models.GarminStressDaily,
        "date_field": models.GarminStressDaily.stress_date,
        "value_field": models.GarminStressDaily.overall_stress_level,
        "higher_is_better": False,
        "label": "overnight stress",
    },
}


def _format_period_label(start_date: dt.date, end_date: dt.date) -> str:
    return f"{start_date.day} {start_date.strftime('%b')} - {end_date.day} {end_date.strftime('%b')}"


def _safe_round(value: float | None, digits: int = 2) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def _mark_highest(entries: list[dict]) -> list[dict]:
    if not entries:
        return entries
    strongest = max(entries, key=lambda item: abs(float(item["delta"])))
    strongest_name = strongest["activity"]
    for entry in entries:
        entry["highest"] = entry["activity"] == strongest_name
    return entries


def _is_sleep_category(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.strip().lower()
    return any(token in lowered for token in _SLEEP_CATEGORY_TOKENS)


@router.get("")
def get_lifestyle_impact(
    metric: str = Query(..., pattern="^(sleep_score|overnight_hrv|overnight_stress)$"),
    days: int = Query(28, ge=7, le=84),
    db: Session = Depends(get_db),
):
    config = _METRIC_CONFIG[metric]

    end_date = dt.datetime.now(dt.timezone.utc).date()
    start_date = end_date - dt.timedelta(days=days - 1)

    metric_rows = (
        db.query(config["date_field"], config["value_field"])
        .filter(config["date_field"] >= start_date)
        .filter(config["date_field"] <= end_date)
        .filter(config["value_field"].isnot(None))
        .all()
    )

    metric_by_date: dict[dt.date, float] = {
        row_date: float(value) for row_date, value in metric_rows if value is not None
    }
    metric_values = list(metric_by_date.values())

    if not metric_values:
        return {
            "metric": metric,
            "period_label": _format_period_label(start_date, end_date),
            "avg_value": None,
            "positive_impact": [],
            "negative_impact": [],
            "minimal_impact": [],
            "threshold": None,
            "sample_days": 0,
        }

    baseline = statistics.mean(metric_values)
    std_dev = statistics.pstdev(metric_values) if len(metric_values) > 1 else 0.0
    threshold = std_dev * 0.05

    mood_rows = (
        db.query(models.Mood)
        .options(selectinload(models.Mood.activities).selectinload(models.Activity.category))
        .filter(func.date(models.Mood.timestamp) >= start_date)
        .filter(func.date(models.Mood.timestamp) <= end_date)
        .all()
    )

    activity_dates: dict[str, set[dt.date]] = defaultdict(set)
    for mood in mood_rows:
        mood_date = mood.timestamp.date()
        for activity in mood.activities:
            if not _is_sleep_category(activity.category.name if activity.category else None):
                continue
            name = (activity.name or "").strip()
            if name:
                activity_dates[name].add(mood_date)

    positive: list[dict] = []
    negative: list[dict] = []
    minimal: list[dict] = []

    for activity_name, dates in activity_dates.items():
        observed_values = [metric_by_date[d] for d in dates if d in metric_by_date]
        if len(observed_values) < 3:
            continue

        activity_mean = statistics.mean(observed_values)
        delta = activity_mean - baseline
        adjusted_delta = delta if config["higher_is_better"] else -delta

        entry = {
            "activity": activity_name,
            "delta": _safe_round(delta, 2),
            "sample_size": len(observed_values),
            "highest": False,
        }

        if adjusted_delta > threshold:
            positive.append(entry)
        elif adjusted_delta < -threshold:
            negative.append(entry)
        else:
            minimal.append(entry)

    positive.sort(key=lambda item: float(item["delta"]), reverse=True)
    negative.sort(key=lambda item: float(item["delta"]))
    minimal.sort(key=lambda item: abs(float(item["delta"])), reverse=True)

    _mark_highest(positive)
    _mark_highest(negative)
    _mark_highest(minimal)

    return {
        "metric": metric,
        "period_label": _format_period_label(start_date, end_date),
        "avg_value": _safe_round(baseline, 2),
        "positive_impact": positive,
        "negative_impact": negative,
        "minimal_impact": minimal,
        "threshold": _safe_round(threshold, 4),
        "sample_days": len(metric_values),
    }
