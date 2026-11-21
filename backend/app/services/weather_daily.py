"""Daily weather (air pressure and temperature) at the owner's home area, from Open-Meteo.

Weather saved on mood entries only exists when the phone shared its location at the
moment of logging. This keeps one row per day for every day instead, so the headache
report can compare weather on headache days and clear days. Open-Meteo is free and
needs no key. Only a rounded home position (about 1 km) is ever sent.
"""

import datetime as dt
import json
import logging
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict

from sqlalchemy.orm import Session

from .. import models
from .insight_dates import UK_TZ

logger = logging.getLogger("app.weather_daily")

HOME_LOCATION_KEY = "home_location"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# The archive lags a few days behind; the forecast service covers the recent days.
RECENT_DAYS = 10
# Don't backfill further back than this, however old the first mood entry is.
MAX_BACKFILL_DAYS = 3 * 365
ARCHIVE_CHUNK_DAYS = 366
LOCATION_DECIMALS = 2


def round_location(latitude: float, longitude: float) -> tuple[float, float]:
    return round(latitude, LOCATION_DECIMALS), round(longitude, LOCATION_DECIMALS)


def get_home_location(db: Session) -> dict | None:
    row = db.get(models.AppSetting, HOME_LOCATION_KEY)
    value = row.value if row is not None else None
    if not isinstance(value, dict):
        return None
    try:
        return {"latitude": float(value["latitude"]), "longitude": float(value["longitude"])}
    except (KeyError, TypeError, ValueError):
        return None


def set_home_location(db: Session, latitude: float, longitude: float) -> dict:
    lat, lon = round_location(latitude, longitude)
    value = {"latitude": lat, "longitude": lon}
    row = db.get(models.AppSetting, HOME_LOCATION_KEY)
    if row is None:
        db.add(models.AppSetting(key=HOME_LOCATION_KEY, value=value))
    else:
        row.value = value
    db.commit()
    return value


def _http_get_json(url: str, params: dict) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": "SleepWellnessTracker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def daily_from_hourly(payload: dict) -> dict[dt.date, dict]:
    """Turn Open-Meteo hourly readings (already in UK local time) into one summary per day."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    pressures = hourly.get("pressure_msl") or []
    temps = hourly.get("temperature_2m") or []
    by_day_pressure: dict[dt.date, list[float]] = defaultdict(list)
    by_day_temp: dict[dt.date, list[float]] = defaultdict(list)
    for idx, stamp in enumerate(times):
        try:
            day = dt.date.fromisoformat(str(stamp)[:10])
        except ValueError:
            continue
        pressure = pressures[idx] if idx < len(pressures) else None
        temp = temps[idx] if idx < len(temps) else None
        if isinstance(pressure, (int, float)):
            by_day_pressure[day].append(float(pressure))
        if isinstance(temp, (int, float)):
            by_day_temp[day].append(float(temp))

    days: dict[dt.date, dict] = {}
    for day in set(by_day_pressure) | set(by_day_temp):
        pressure_vals = by_day_pressure.get(day, [])
        temp_vals = by_day_temp.get(day, [])
        # Need most of the day's hours, or the average and max would be misleading.
        days[day] = {
            "pressure_msl_mean": round(statistics.fmean(pressure_vals), 1) if len(pressure_vals) >= 18 else None,
            "temperature_max_c": round(max(temp_vals), 2) if len(temp_vals) >= 18 else None,
            "temperature_min_c": round(min(temp_vals), 2) if len(temp_vals) >= 18 else None,
        }
    return days


def _fetch_range(url: str, latitude: float, longitude: float, extra: dict) -> dict[dt.date, dict]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "pressure_msl,temperature_2m",
        "timezone": "Europe/London",
        **extra,
    }
    return daily_from_hourly(_http_get_json(url, params))


def _store_days(db: Session, days: dict[dt.date, dict], last_complete_day: dt.date) -> int:
    stored = 0
    for day, values in days.items():
        if day > last_complete_day or all(v is None for v in values.values()):
            continue
        row = db.query(models.WeatherDaily).filter(models.WeatherDaily.weather_date == day).first()
        if row is None:
            row = models.WeatherDaily(weather_date=day)
            db.add(row)
        row.pressure_msl_mean = values["pressure_msl_mean"]
        row.temperature_max_c = values["temperature_max_c"]
        row.temperature_min_c = values["temperature_min_c"]
        stored += 1
    db.commit()
    return stored


def _backfill_start(db: Session, today: dt.date) -> dt.date:
    earliest = db.query(models.Mood.timestamp).order_by(models.Mood.timestamp.asc()).first()
    floor = today - dt.timedelta(days=MAX_BACKFILL_DAYS)
    if earliest is None:
        return max(floor, today - dt.timedelta(days=90))
    return max(floor, earliest[0].astimezone(UK_TZ).date() - dt.timedelta(days=1))


def sync_weather(db: Session, today: dt.date | None = None) -> dict:
    """Fill in missing days back to the first mood entry, and refresh the last few days.

    Safe to run often: older days already stored are not fetched again.
    """
    location = get_home_location(db)
    if location is None:
        return {"status": "no_home_location", "stored": 0}
    lat, lon = location["latitude"], location["longitude"]
    today = today or dt.datetime.now(UK_TZ).date()
    yesterday = today - dt.timedelta(days=1)
    recent_start = today - dt.timedelta(days=RECENT_DAYS)
    stored = 0

    # 1. Older days from the archive, only where missing.
    start = _backfill_start(db, today)
    archive_end = recent_start - dt.timedelta(days=1)
    if start <= archive_end:
        have = {
            d
            for (d,) in db.query(models.WeatherDaily.weather_date).filter(
                models.WeatherDaily.weather_date >= start,
                models.WeatherDaily.weather_date <= archive_end,
                models.WeatherDaily.pressure_msl_mean.isnot(None),
            )
        }
        missing = [start + dt.timedelta(days=i) for i in range((archive_end - start).days + 1)]
        missing = [d for d in missing if d not in have]
        if missing:
            chunk_start = missing[0]
            final = missing[-1]
            while chunk_start <= final:
                chunk_end = min(chunk_start + dt.timedelta(days=ARCHIVE_CHUNK_DAYS - 1), final)
                days = _fetch_range(
                    ARCHIVE_URL,
                    lat,
                    lon,
                    {"start_date": chunk_start.isoformat(), "end_date": chunk_end.isoformat()},
                )
                stored += _store_days(db, days, yesterday)
                chunk_start = chunk_end + dt.timedelta(days=1)

    # 2. Recent days from the forecast service (always refreshed; today is skipped as incomplete).
    days = _fetch_range(FORECAST_URL, lat, lon, {"past_days": RECENT_DAYS + 1, "forecast_days": 1})
    stored += _store_days(db, {d: v for d, v in days.items() if d >= recent_start}, yesterday)
    return {"status": "ok", "stored": stored}


def weather_status(db: Session) -> dict:
    count = db.query(models.WeatherDaily).filter(models.WeatherDaily.pressure_msl_mean.isnot(None)).count()
    first = db.query(models.WeatherDaily.weather_date).order_by(models.WeatherDaily.weather_date.asc()).first()
    last = db.query(models.WeatherDaily.weather_date).order_by(models.WeatherDaily.weather_date.desc()).first()
    return {
        "home_location_set": get_home_location(db) is not None,
        "days_stored": count,
        "first_date": first[0].isoformat() if first else None,
        "last_date": last[0].isoformat() if last else None,
    }
