import datetime as dt
import logging
import os
import threading
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from .database import SessionLocal
from .routes import mood, categories, activities, garmin
from .services.garmin_sync import sync_sleep_if_due

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
GARMIN_AUTOSYNC_POLL_SECONDS = _env_int("GARMIN_AUTOSYNC_POLL_SECONDS", 300, 30)

_autosync_stop = threading.Event()
_autosync_thread: threading.Thread | None = None


def _after_8am_uk(now_local: dt.datetime) -> bool:
    return now_local.time() >= dt.time(hour=8, minute=0)


def _garmin_sleep_autosync_loop() -> None:
    logger.info(
        "Garmin sleep autosync loop started; enabled=%s poll_seconds=%s",
        GARMIN_AUTOSYNC_ENABLED,
        GARMIN_AUTOSYNC_POLL_SECONDS,
    )
    while not _autosync_stop.is_set():
        now_local = dt.datetime.now(dt.timezone.utc).astimezone(UK_TZ)
        if _after_8am_uk(now_local):
            db = SessionLocal()
            try:
                result = sync_sleep_if_due(db, force=False)
                status = result.get("status")
                if status in {"ok", "partial", "error"}:
                    logger.info("Garmin sleep autosync run result: %s", result)
            except Exception:
                logger.exception("Garmin sleep autosync loop failed")
            finally:
                db.close()
        _autosync_stop.wait(GARMIN_AUTOSYNC_POLL_SECONDS)


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
