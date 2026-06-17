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


def _parse_activity_ids(raw_activity_ids: str | None) -> set[int]:
    if not raw_activity_ids:
        return set()
    parsed: set[int] = set()
    for chunk in raw_activity_ids.split(","):
        trimmed = chunk.strip()
        if not trimmed:
            continue
        try:
            value = int(trimmed)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid activity id: {trimmed}") from exc
        if value > 0:
            parsed.add(value)
    return parsed


def _parse_mood_row_mode(raw_mode: str | None) -> str:
    mode = (raw_mode or "entry").strip().lower()
    if mode not in {"entry", "daily"}:
        raise HTTPException(status_code=400, detail="mood_row_mode must be one of: entry, daily")
    return mode


@router.get("/csv")
def export_csv(
    sources: str = Query(..., description="Comma-separated sources"),
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    activity_ids: str | None = Query(default=None, description="Optional comma-separated mood activity IDs"),
<<<<<<< HEAD
    include_notes: bool = Query(default=True, description="Include mood notes in the export"),
=======
    mood_row_mode: str = Query(default="entry", description="Mood row format: entry or daily"),
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)
    db: Session = Depends(get_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    selected_sources = _parse_sources(sources)
    selected_activity_ids = _parse_activity_ids(activity_ids)
    selected_mood_row_mode = _parse_mood_row_mode(mood_row_mode)
    use_mood_entry_rows = "mood" in selected_sources and selected_mood_row_mode == "entry"

    allowed_dates: set[dt.date] = set()
    if selected_activity_ids:
        mood_date_rows = (
            db.query(func.date(models.Mood.timestamp))
            .join(models.Mood.activities)
            .filter(func.date(models.Mood.timestamp) >= start_date)
            .filter(func.date(models.Mood.timestamp) <= end_date)
            .filter(models.Activity.id.in_(selected_activity_ids))
            .distinct()
            .all()
        )
        allowed_dates = {row_date for (row_date,) in mood_date_rows if isinstance(row_date, dt.date)}

    by_date: dict[str, dict[str, object]] = {}
    mood_entry_rows: list[dict[str, object]] = []
    mood_entry_rows_by_date: dict[dt.date, list[dict[str, object]]] = defaultdict(list)
    column_order: list[str] = []

    def ensure_row(date_value: dt.date) -> dict[str, object]:
        iso = date_value.isoformat()
        if iso not in by_date:
            by_date[iso] = {"Date": iso}
        return by_date[iso]

    def add_columns(columns: list[str]) -> None:
        for column in columns:
            if column not in column_order:
                column_order.append(column)

    def targets_for_date(date_value: dt.date) -> list[dict[str, object]]:
        if use_mood_entry_rows:
            return mood_entry_rows_by_date.get(date_value, [])
        return [ensure_row(date_value)]

    def date_allowed(target_date: dt.date) -> bool:
        if use_mood_entry_rows:
            return target_date in mood_entry_rows_by_date
        if not selected_activity_ids:
            return True
        return target_date in allowed_dates

    if "mood" in selected_sources and use_mood_entry_rows:
        add_columns(["mood_entry_id", "mood_timestamp", "mood_score", "mood_activities", "mood_notes"])
        query = (
            db.query(models.Mood)
            .options(selectinload(models.Mood.activities))
            .filter(func.date(models.Mood.timestamp) >= start_date)
            .filter(func.date(models.Mood.timestamp) <= end_date)
        )
        if selected_activity_ids:
            query = (
                query.join(models.Mood.activities)
                .filter(models.Activity.id.in_(selected_activity_ids))
                .distinct()
            )

        rows = query.order_by(models.Mood.timestamp.asc(), models.Mood.id.asc()).all()
        for row in rows:
            row_date = row.timestamp.date()
            activity_names = []
            for activity in row.activities:
                if selected_activity_ids and activity.id not in selected_activity_ids:
                    continue
                if activity.name and activity.name.strip():
                    activity_names.append(activity.name.strip())

            export_row = {
                "date": row_date.isoformat(),
                "mood_entry_id": row.id,
                "mood_timestamp": row.timestamp.isoformat(),
                "mood_score": int(row.mood_score) if row.mood_score is not None else None,
                "mood_activities": ", ".join(sorted(set(activity_names))),
                "mood_notes": (row.notes or "").strip() or None,
            }
            mood_entry_rows.append(export_row)
            mood_entry_rows_by_date[row_date].append(export_row)

    if "sleep" in selected_sources:
        add_columns([
            "Sleep Score",
            "Total Sleep (min)",
            "Deep Sleep (min)",
            "Light Sleep (min)",
            "REM Sleep (min)",
            "Awake (min)",
        ])
        rows = (
            db.query(models.GarminSleepDaily)
            .filter(models.GarminSleepDaily.sleep_date >= start_date)
            .filter(models.GarminSleepDaily.sleep_date <= end_date)
            .all()
        )
        for row in rows:
            if not date_allowed(row.sleep_date):
                continue
<<<<<<< HEAD
            target = ensure_row(row.sleep_date)
            target["Sleep Score"] = row.sleep_score
            target["Total Sleep (min)"] = row.total_sleep_minutes
            target["Deep Sleep (min)"] = row.deep_sleep_minutes
            target["Light Sleep (min)"] = row.light_sleep_minutes
            target["REM Sleep (min)"] = row.rem_sleep_minutes
            target["Awake (min)"] = row.awake_minutes
=======
            for target in targets_for_date(row.sleep_date):
                target["sleep_score"] = row.sleep_score
                target["total_sleep_minutes"] = row.total_sleep_minutes
                target["deep_sleep_minutes"] = row.deep_sleep_minutes
                target["light_sleep_minutes"] = row.light_sleep_minutes
                target["rem_sleep_minutes"] = row.rem_sleep_minutes
                target["awake_minutes"] = row.awake_minutes
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)

    if "hrv" in selected_sources:
        add_columns(["HRV Weekly Avg", "HRV Status"])
        rows = (
            db.query(models.GarminHRVDaily)
            .filter(models.GarminHRVDaily.hrv_date >= start_date)
            .filter(models.GarminHRVDaily.hrv_date <= end_date)
            .all()
        )
        for row in rows:
            if not date_allowed(row.hrv_date):
                continue
<<<<<<< HEAD
            target = ensure_row(row.hrv_date)
            target["HRV Weekly Avg"] = row.weekly_avg
            target["HRV Status"] = row.status
=======
            for target in targets_for_date(row.hrv_date):
                target["hrv_weekly_avg"] = row.weekly_avg
                target["hrv_status"] = row.status
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)

    if "stress" in selected_sources:
        add_columns([
            "Stress Level",
            "Stress: Rest (min)",
            "Stress: Low (min)",
            "Stress: Medium (min)",
            "Stress: High (min)",
        ])
        rows = (
            db.query(models.GarminStressDaily)
            .filter(models.GarminStressDaily.stress_date >= start_date)
            .filter(models.GarminStressDaily.stress_date <= end_date)
            .all()
        )
        for row in rows:
            if not date_allowed(row.stress_date):
                continue
<<<<<<< HEAD
            target = ensure_row(row.stress_date)
            target["Stress Level"] = row.overall_stress_level
            target["Stress: Rest (min)"] = row.rest_stress_duration
            target["Stress: Low (min)"] = row.low_stress_duration
            target["Stress: Medium (min)"] = row.medium_stress_duration
            target["Stress: High (min)"] = row.high_stress_duration
=======
            for target in targets_for_date(row.stress_date):
                target["stress_overall_level"] = row.overall_stress_level
                target["stress_rest_minutes"] = row.rest_stress_duration
                target["stress_low_minutes"] = row.low_stress_duration
                target["stress_medium_minutes"] = row.medium_stress_duration
                target["stress_high_minutes"] = row.high_stress_duration
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)

    if "body_battery" in selected_sources:
        add_columns([
            "Body Battery: Morning",
            "Body Battery: End of Day",
            "Body Battery: Peak",
            "Body Battery: Low",
        ])
        rows = (
            db.query(models.GarminBodyBatteryDaily)
            .filter(models.GarminBodyBatteryDaily.battery_date >= start_date)
            .filter(models.GarminBodyBatteryDaily.battery_date <= end_date)
            .all()
        )
        for row in rows:
            if not date_allowed(row.battery_date):
                continue
<<<<<<< HEAD
            target = ensure_row(row.battery_date)
            target["Body Battery: Morning"] = row.morning_value
            target["Body Battery: End of Day"] = row.end_of_day_value
            target["Body Battery: Peak"] = row.peak_value
            target["Body Battery: Low"] = row.low_value
=======
            for target in targets_for_date(row.battery_date):
                target["body_battery_morning"] = row.morning_value
                target["body_battery_end_of_day"] = row.end_of_day_value
                target["body_battery_peak"] = row.peak_value
                target["body_battery_low"] = row.low_value
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)

    if "rhr" in selected_sources:
        add_columns([
            "Resting Heart Rate (bpm)",
            "Min Heart Rate (bpm)",
            "Max Heart Rate (bpm)",
        ])
        rows = (
            db.query(models.GarminRestingHeartRateDaily)
            .filter(models.GarminRestingHeartRateDaily.heart_rate_date >= start_date)
            .filter(models.GarminRestingHeartRateDaily.heart_rate_date <= end_date)
            .all()
        )
        for row in rows:
            if not date_allowed(row.heart_rate_date):
                continue
<<<<<<< HEAD
            target = ensure_row(row.heart_rate_date)
            target["Resting Heart Rate (bpm)"] = row.resting_heart_rate
            target["Min Heart Rate (bpm)"] = row.min_heart_rate
            target["Max Heart Rate (bpm)"] = row.max_heart_rate
=======
            for target in targets_for_date(row.heart_rate_date):
                target["resting_heart_rate"] = row.resting_heart_rate
                target["min_heart_rate"] = row.min_heart_rate
                target["max_heart_rate"] = row.max_heart_rate
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)

    if "hydration" in selected_sources:
        add_columns(["Hydration Consumed (ml)", "Hydration Goal (ml)"])
        rows = (
            db.query(models.GarminHydrationDaily)
            .filter(models.GarminHydrationDaily.hydration_date >= start_date)
            .filter(models.GarminHydrationDaily.hydration_date <= end_date)
            .all()
        )
        for row in rows:
            if not date_allowed(row.hydration_date):
                continue
<<<<<<< HEAD
            target = ensure_row(row.hydration_date)
            target["Hydration Consumed (ml)"] = row.consumed_ml
            target["Hydration Goal (ml)"] = row.goal_ml
=======
            for target in targets_for_date(row.hydration_date):
                target["hydration_consumed_ml"] = row.consumed_ml
                target["hydration_goal_ml"] = row.goal_ml
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)

    if "steps" in selected_sources:
        add_columns(["Total Steps", "Steps Distance (m)", "Steps Calories Burned"])
        rows = (
            db.query(models.GarminStepsDaily)
            .filter(models.GarminStepsDaily.steps_date >= start_date)
            .filter(models.GarminStepsDaily.steps_date <= end_date)
            .all()
        )
        for row in rows:
            if not date_allowed(row.steps_date):
                continue
<<<<<<< HEAD
            target = ensure_row(row.steps_date)
            target["Total Steps"] = row.total_steps
            target["Steps Distance (m)"] = row.distance_meters
            target["Steps Calories Burned"] = row.calories_burned
=======
            for target in targets_for_date(row.steps_date):
                target["steps_total"] = row.total_steps
                target["steps_distance_meters"] = row.distance_meters
                target["steps_calories_burned"] = row.calories_burned
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)

    if "activities" in selected_sources:
        add_columns([
            "Garmin Activity Count",
            "Garmin Activity Names",
            "Garmin Activity Types",
            "Garmin Total Distance (m)",
            "Garmin Total Duration (sec)",
            "Garmin Total Calories",
        ])
        rows = (
            db.query(models.GarminActivity)
            .filter(models.GarminActivity.activity_date >= start_date)
            .filter(models.GarminActivity.activity_date <= end_date)
            .all()
        )
        grouped: dict[dt.date, list[models.GarminActivity]] = defaultdict(list)
        for row in rows:
            if not date_allowed(row.activity_date):
                continue
            grouped[row.activity_date].append(row)

        for activity_date, date_rows in grouped.items():
<<<<<<< HEAD
            target = ensure_row(activity_date)
            activity_names = [
                activity.activity_name.strip()
                for activity in date_rows
                if activity.activity_name and activity.activity_name.strip()
            ]
=======
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)
            activity_types = sorted(
                {
                    activity.activity_type.strip()
                    for activity in date_rows
                    if activity.activity_type and activity.activity_type.strip()
                }
            )
<<<<<<< HEAD
            target["Garmin Activity Count"] = len(date_rows)
            target["Garmin Activity Names"] = ", ".join(activity_names)
            target["Garmin Activity Types"] = ", ".join(activity_types)
            target["Garmin Total Distance (m)"] = sum(int(activity.distance_meters or 0) for activity in date_rows)
            target["Garmin Total Duration (sec)"] = sum(int(activity.duration_seconds or 0) for activity in date_rows)
            target["Garmin Total Calories"] = sum(int(activity.calories or 0) for activity in date_rows)

    if "mood" in selected_sources:
        mood_columns = ["Mood Score", "Mood Activities", "Mood Entries"]
        if include_notes:
            mood_columns.insert(2, "Mood Notes")
        add_columns(mood_columns)
=======
            for target in targets_for_date(activity_date):
                target["garmin_activity_count"] = len(date_rows)
                target["garmin_activity_types"] = ", ".join(activity_types)
                target["garmin_activity_distance_meters"] = sum(int(activity.distance_meters or 0) for activity in date_rows)
                target["garmin_activity_duration_seconds"] = sum(int(activity.duration_seconds or 0) for activity in date_rows)
                target["garmin_activity_calories"] = sum(int(activity.calories or 0) for activity in date_rows)

    if "mood" in selected_sources and not use_mood_entry_rows:
        add_columns(["mood_score", "mood_activities", "mood_notes", "mood_entries"])
>>>>>>> 92aa984 (feat(export): add activity-specific entry-level CSV rows)
        query = (
            db.query(models.Mood)
            .options(selectinload(models.Mood.activities))
            .filter(func.date(models.Mood.timestamp) >= start_date)
            .filter(func.date(models.Mood.timestamp) <= end_date)
        )
        if selected_activity_ids:
            query = (
                query.join(models.Mood.activities)
                .filter(models.Activity.id.in_(selected_activity_ids))
                .distinct()
            )
        rows = query.all()

        grouped_scores: dict[dt.date, list[int]] = defaultdict(list)
        grouped_activities: dict[dt.date, set[str]] = defaultdict(set)
        grouped_notes: dict[dt.date, list[str]] = defaultdict(list)
        grouped_entries: dict[dt.date, int] = defaultdict(int)

        for row in rows:
            row_date = row.timestamp.date()
            if not date_allowed(row_date):
                continue
            grouped_entries[row_date] += 1
            if row.mood_score is not None:
                grouped_scores[row_date].append(int(row.mood_score))
            if row.notes:
                text = row.notes.strip()
                if text:
                    grouped_notes[row_date].append(text)
            for activity in row.activities:
                if selected_activity_ids and activity.id not in selected_activity_ids:
                    continue
                if activity.name and activity.name.strip():
                    grouped_activities[row_date].add(activity.name.strip())

        for mood_date in set(grouped_entries.keys()):
            target = ensure_row(mood_date)
            scores = grouped_scores.get(mood_date, [])
            target["Mood Score"] = round(sum(scores) / len(scores), 2) if scores else None
            target["Mood Activities"] = ", ".join(sorted(grouped_activities.get(mood_date, set())))
            if include_notes:
                target["Mood Notes"] = " | ".join(grouped_notes.get(mood_date, []))
            target["Mood Entries"] = grouped_entries[mood_date]

    header = ["Date", *column_order]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=header, extrasaction="ignore")
    writer.writeheader()

    if use_mood_entry_rows:
        for row in mood_entry_rows:
            writer.writerow({column: row.get(column) for column in header})
    else:
        for date_key in sorted(by_date.keys()):
            row = by_date[date_key]
            writer.writerow({column: row.get(column) for column in header})

    csv_payload = output.getvalue()
    output.close()

    filename = f"export_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([csv_payload]), media_type="text/csv", headers=headers)
