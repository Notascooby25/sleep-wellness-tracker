"""Set up a throwaway app for the smoke tests.

The tests need a real Postgres, because production uses it and SQLite hides
errors. Point TEST_DATABASE_URL at a throwaway database. The app's background
workers don't run, as they start with the server, not on import.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:test@localhost:55432/sleeptest"
)
os.environ["APP_PASSWORD"] = "test-password"
os.environ["GARMIN_AUTOSYNC_ENABLED"] = "false"
os.environ.setdefault("MOOD_IMAGE_STORAGE_PATH", tempfile.mkdtemp())

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


_CLEANED_TABLES = (
    "mood_activity_details",
    "mood_activities",
    "moods",
    "activities",
    "categories",
    "garmin_sleep_daily",
    "garmin_hrv_daily",
    "garmin_stress_daily",
    "garmin_resting_heart_rate_daily",
    "garmin_steps_daily",
    "garmin_activities",
    "garmin_hydration_daily",
)


@pytest.fixture
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _assert_throwaway_database(url: str) -> None:
    name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if "test" not in name.lower():
        raise RuntimeError(f"Refusing to wipe tables in database '{name}': its name must contain 'test'.")


@pytest.fixture
def clean_db():
    from sqlalchemy import text

    from app.database import engine

    _assert_throwaway_database(engine.url.render_as_string(hide_password=True))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(_CLEANED_TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def signed_in(client):
    response = client.post("/auth/login", json={"password": "test-password"})
    assert response.status_code == 200
    return client
