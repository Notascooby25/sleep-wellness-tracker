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


@pytest.fixture
def signed_in(client):
    response = client.post("/auth/login", json={"password": "test-password"})
    assert response.status_code == 200
    return client
