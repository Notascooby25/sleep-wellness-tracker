import csv
import datetime as dt
import io
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..database import get_db

router = APIRouter(prefix="/export", tags=["export"])

_ALLOWED_SOURCES = {
    "mood",
    "sleep",
    "hrv",
    "stress",
    "body_battery",
    "rhr",
    "hydration",
    "steps",
    "activities",
}


def _parse_sources(raw_sources: str) -> list[str]:
    values = [chunk.strip().lower() for chunk in raw_sources.split(",") if chunk.strip()]
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)

    if not unique_values:
        raise HTTPException(status_code=400, detail="At least one source is required")

    invalid = [source for source in unique_values if source not in _ALLOWED_SOURCES]
    if invalid:
        allowed = ", ".join(sorted(_ALLOWED_SOURCES))
        raise HTTPException(status_code=400, detail=f"Unknown source(s): {', '.join(invalid)}. Allowed: {allowed}")

    return unique_values


@router.get("/csv")
def export_csv(
    sources: str = Query(..., description="Comma-separated sources"),
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    selected_sources = _parse_sources(sources)

    by_date: dict[str, dict[str, object]] = {}
    column_order: list[str] = []

    def ensure_row(date_value: dt.date) -> dict[str, object]:
        iso = date_value.isoformat()
        if iso not in by_date:
            by_date[iso] = {"date": iso}
        return by_date[iso]

    def add_columns(columns: list[str]) -> None:
        for column in columns:
            if column not in column_order:
                column_order.append(column)

    if "sleep" in selected_sources:
        add_columns([
            "sleep_score",
            "total_sleep_minutes",
            "deep_sleep_minutes",
            "light_sleep_minutes",
            "rem_sleep_minutes",
            "awake_minutes",
        ])
        rows = (
            db.query(models.GarminSleepDaily)
            .filter(models.GarminSleepDaily.sleep_date >= start_date)
            .filter(models.GarminSleepDaily.sleep_date <= end_date)
            .all()
        )
        for row in rows:
            target = ensure_row(row.sleep_date)
            target["sleep_score"] = row.sleep_score
            target["total_sleep_minutes"] = row.total_sleep_minutes
            target["deep_sleep_minutes"] = row.deep_sleep_minutes
            target["light_sleep_minutes"] = row.light_sleep_minutes
            target["rem_sleep_minutes"] = row.rem_sleep_minutes
            target["awake_minutes"] = row.awake_minutes

    if "hrv" in selected_sources:
        add_columns(["hrv_weekly_avg", "hrv_status"])
        rows = (
            db.query(models.GarminHRVDaily)
            .filter(models.GarminHRVDaily.hrv_date >= start_date)
            .filter(models.GarminHRVDaily.hrv_date <= end_date)
            .all()
        )
        for row in rows:
            target = ensure_row(row.hrv_date)
            target["hrv_weekly_avg"] = row.weekly_avg
            target["hrv_status"] = row.status

    if "stress" in selected_sources:
        add_columns([
            "stress_overall_level",
            "stress_rest_minutes",
            "stress_low_minutes",
            "stress_medium_minutes",
            "stress_high_minutes",
        ])
        rows = (
            db.query(models.GarminStressDaily)
            .filter(models.GarminStressDaily.stress_date >= start_date)
            .filter(models.GarminStressDaily.stress_date <= end_date)
            .all()
        )
        for row in rows:
            target = ensure_row(row.stress_date)
            target["stress_overall_level"] = row.overall_stress_level
            target["stress_rest_minutes"] = row.rest_stress_duration
            target["stress_low_minutes"] = row.low_stress_duration
            target["stress_medium_minutes"] = row.medium_stress_duration
            target["stress_high_minutes"] = row.high_stress_duration

    if "body_battery" in selected_sources:
        add_columns(["body_battery_morning", "body_battery_end_of_day", "body_battery_peak", "body_battery_low"])
        rows = (
            db.query(models.GarminBodyBatteryDaily)
            .filter(models.GarminBodyBatteryDaily.battery_date >= start_date)
            .filter(models.GarminBodyBatteryDaily.battery_date <= end_date)
            .all()
        )
        for row in rows:
            target = ensure_row(row.battery_date)
            target["body_battery_morning"] = row.morning_value
            target["body_battery_end_of_day"] = row.end_of_day_value
            target["body_battery_peak"] = row.peak_value
            target["body_battery_low"] = row.low_value

    if "rhr" in selected_sources:
        add_columns(["resting_heart_rate", "min_heart_rate", "max_heart_rate"])
        rows = (
            db.query(models.GarminRestingHeartRateDaily)
            .filter(models.GarminRestingHeartRateDaily.heart_rate_date >= start_date)
            .filter(models.GarminRestingHeartRateDaily.heart_rate_date <= end_date)
            .all()
        )
        for row in rows:
            target = ensure_row(row.heart_rate_date)
            target["resting_heart_rate"] = row.resting_heart_rate
            target["min_heart_rate"] = row.min_heart_rate
            target["max_heart_rate"] = row.max_heart_rate

    if "hydration" in selected_sources:
        add_columns(["hydration_consumed_ml", "hydration_goal_ml"])
        rows = (
            db.query(models.GarminHydrationDaily)
            .filter(models.GarminHydrationDaily.hydration_date >= start_date)
            .filter(models.GarminHydrationDaily.hydration_date <= end_date)
            .all()
        )
        for row in rows:
            target = ensure_row(row.hydration_date)
            target["hydration_consumed_ml"] = row.consumed_ml
            target["hydration_goal_ml"] = row.goal_ml

    if "steps" in selected_sources:
        add_columns(["steps_total", "steps_distance_meters", "steps_calories_burned"])
        rows = (
            db.query(models.GarminStepsDaily)
            .filter(models.GarminStepsDaily.steps_date >= start_date)
            .filter(models.GarminStepsDaily.steps_date <= end_date)
            .all()
        )
        for row in rows:
            target = ensure_row(row.steps_date)
            target["steps_total"] = row.total_steps
            target["steps_distance_meters"] = row.distance_meters
            target["steps_calories_burned"] = row.calories_burned

    if "activities" in selected_sources:
        add_columns([
            "garmin_activity_count",
            "garmin_activity_types",
            "garmin_activity_distance_meters",
            "garmin_activity_duration_seconds",
            "garmin_activity_calories",
        ])
        rows = (
            db.query(models.GarminActivity)
            .filter(models.GarminActivity.activity_date >= start_date)
            .filter(models.GarminActivity.activity_date <= end_date)
            .all()
        )
        grouped: dict[dt.date, list[models.GarminActivity]] = defaultdict(list)
        for row in rows:
            grouped[row.activity_date].append(row)

        for activity_date, date_rows in grouped.items():
            target = ensure_row(activity_date)
            activity_types = sorted(
                {
                    activity.activity_type.strip()
                    for activity in date_rows
                    if activity.activity_type and activity.activity_type.strip()
                }
            )
            target["garmin_activity_count"] = len(date_rows)
            target["garmin_activity_types"] = ", ".join(activity_types)
            target["garmin_activity_distance_meters"] = sum(int(activity.distance_meters or 0) for activity in date_rows)
            target["garmin_activity_duration_seconds"] = sum(int(activity.duration_seconds or 0) for activity in date_rows)
            target["garmin_activity_calories"] = sum(int(activity.calories or 0) for activity in date_rows)

    if "mood" in selected_sources:
        add_columns(["mood_score", "mood_activities", "mood_notes", "mood_entries"])
        rows = (
            db.query(models.Mood)
            .options(selectinload(models.Mood.activities))
            .filter(func.date(models.Mood.timestamp) >= start_date)
            .filter(func.date(models.Mood.timestamp) <= end_date)
            .all()
        )

        grouped_scores: dict[dt.date, list[int]] = defaultdict(list)
        grouped_activities: dict[dt.date, set[str]] = defaultdict(set)
        grouped_notes: dict[dt.date, list[str]] = defaultdict(list)
        grouped_entries: dict[dt.date, int] = defaultdict(int)

        for row in rows:
            row_date = row.timestamp.date()
            grouped_entries[row_date] += 1
            if row.mood_score is not None:
                grouped_scores[row_date].append(int(row.mood_score))
            if row.notes:
                text = row.notes.strip()
                if text:
                    grouped_notes[row_date].append(text)
            for activity in row.activities:
                if activity.name and activity.name.strip():
                    grouped_activities[row_date].add(activity.name.strip())

        for mood_date in set(grouped_entries.keys()):
            target = ensure_row(mood_date)
            scores = grouped_scores.get(mood_date, [])
            target["mood_score"] = round(sum(scores) / len(scores), 2) if scores else None
            target["mood_activities"] = ", ".join(sorted(grouped_activities.get(mood_date, set())))
            target["mood_notes"] = " | ".join(grouped_notes.get(mood_date, []))
            target["mood_entries"] = grouped_entries[mood_date]

    header = ["date", *column_order]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=header, extrasaction="ignore")
    writer.writeheader()

    for date_key in sorted(by_date.keys()):
        row = by_date[date_key]
        writer.writerow({column: row.get(column) for column in header})

    csv_payload = output.getvalue()
    output.close()

    filename = f"export_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([csv_payload]), media_type="text/csv", headers=headers)
