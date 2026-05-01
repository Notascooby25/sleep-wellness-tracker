import datetime as dt
import logging
import os
import threading
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from .database import SessionLocal
from .routes import mood, categories, activities, garmin
from .services.garmin_sync import (
    sync_activities_if_due,
    sync_sleep_if_due,
    sync_body_battery_if_due,
    sync_hrv_if_due,
    sync_resting_heart_rate_if_due,
    sync_stress_if_due,
    sync_hydration_if_due,
)

app = FastAPI()
logger = logging.getLogger("app.main")
UK_TZ = ZoneInfo("Europe/London")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, min_value: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(min_value, int(raw.strip()))
    except Exception:
        logger.warning("Invalid integer for %s=%r, using default %s", name, raw, default)
        return default


GARMIN_AUTOSYNC_ENABLED = _env_bool("GARMIN_AUTOSYNC_ENABLED", True)
# Poll interval — short so we don't miss a scheduled window
_AUTOSYNC_POLL_SECONDS = 60

_autosync_stop = threading.Event()
_autosync_thread: threading.Thread | None = None

# Track the last date we ran each window so we only fire once per day per window.
_morning_synced_date: dt.date | None = None
_evening_synced_date: dt.date | None = None


def _in_morning_window(now_local: dt.datetime) -> bool:
    """08:00 – 09:00 UK — pull overnight data: sleep, HRV, resting HR."""
    return dt.time(8, 0) <= now_local.time() < dt.time(9, 0)


def _in_evening_window(now_local: dt.datetime) -> bool:
    """23:50 – 00:00 UK — pull end-of-day data: body battery, hydration, stress."""
    return now_local.time() >= dt.time(23, 50)


def _garmin_sleep_autosync_loop() -> None:
    global _morning_synced_date, _evening_synced_date

    logger.info("Garmin autosync loop started; enabled=%s", GARMIN_AUTOSYNC_ENABLED)
    while not _autosync_stop.is_set():
        now_local = dt.datetime.now(dt.timezone.utc).astimezone(UK_TZ)
        today = now_local.date()

        if _in_morning_window(now_local) and _morning_synced_date != today:
            db = SessionLocal()
            try:
                logger.info("Garmin morning sync starting (sleep + HRV + resting HR); date=%s", today)
                for fn, label in [
                    (sync_sleep_if_due, "sleep"),
                    (sync_hrv_if_due, "hrv"),
                    (sync_resting_heart_rate_if_due, "rhr"),
                ]:
                    try:
                        result = fn(db, force=False)
                        logger.info("Garmin morning sync %s result: %s", label, result)
                    except Exception:
                        logger.exception("Garmin morning sync failed for %s", label)
                _morning_synced_date = today
            finally:
                db.close()

        elif _in_evening_window(now_local) and _evening_synced_date != today:
            db = SessionLocal()
            try:
                logger.info("Garmin evening sync starting (body battery + hydration + stress + activities); date=%s", today)
                for fn, label in [
                    (sync_body_battery_if_due, "body_battery"),
                    (sync_hydration_if_due, "hydration"),
                    (sync_stress_if_due, "stress"),
                    (sync_activities_if_due, "activities"),
                ]:
                    try:
                        result = fn(db, force=False)
                        logger.info("Garmin evening sync %s result: %s", label, result)
                    except Exception:
                        logger.exception("Garmin evening sync failed for %s", label)
                _evening_synced_date = today
            finally:
                db.close()

        _autosync_stop.wait(_AUTOSYNC_POLL_SECONDS)


@app.on_event("startup")
def _start_background_workers() -> None:
    global _autosync_thread

    if not GARMIN_AUTOSYNC_ENABLED:
        logger.info("Garmin sleep autosync is disabled via GARMIN_AUTOSYNC_ENABLED")
        return

    if _autosync_thread and _autosync_thread.is_alive():
        return

    _autosync_stop.clear()
    _autosync_thread = threading.Thread(target=_garmin_sleep_autosync_loop, name="garmin-sleep-autosync", daemon=True)
    _autosync_thread.start()


@app.on_event("shutdown")
def _stop_background_workers() -> None:
    _autosync_stop.set()
    if _autosync_thread and _autosync_thread.is_alive():
        _autosync_thread.join(timeout=2)

# Routers ALREADY have prefixes inside their files.
# Do NOT add prefixes here.

app.include_router(mood.router)
app.include_router(categories.router)
app.include_router(activities.router)
app.include_router(garmin.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
