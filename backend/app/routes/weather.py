"""Home area for daily weather, and its sync status."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..services.weather_daily import (
    get_home_location,
    set_home_location,
    sync_away_weather,
    sync_weather,
    weather_status,
)

router = APIRouter(prefix="/weather", tags=["weather"])
logger = logging.getLogger("app.weather")


class HomeLocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


def run_weather_sync() -> None:
    # Home and away weather run separately, so a failure in one doesn't hold up the other.
    for label, job in (("Weather sync", sync_weather), ("Away weather sync", sync_away_weather)):
        db = SessionLocal()
        try:
            result = job(db)
            logger.info("%s finished: %s", label, result)
        except Exception:
            logger.exception("%s failed", label)
        finally:
            db.close()


@router.get("/status")
def get_weather_status(db: Session = Depends(get_db)):
    return {**weather_status(db), "home_location": get_home_location(db)}


@router.put("/home-location")
def save_home_location(payload: HomeLocationIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    # Stored weather is kept: changing home (e.g. after moving house) only affects days not
    # yet fetched, so past days keep the weather of where you lived then.
    saved = set_home_location(db, payload.latitude, payload.longitude)
    background.add_task(run_weather_sync)
    return {**weather_status(db), "home_location": saved}


@router.post("/sync")
def trigger_weather_sync(background: BackgroundTasks, db: Session = Depends(get_db)):
    if get_home_location(db) is None:
        raise HTTPException(status_code=400, detail="Set your home area first.")
    background.add_task(run_weather_sync)
    return {"status": "started"}
