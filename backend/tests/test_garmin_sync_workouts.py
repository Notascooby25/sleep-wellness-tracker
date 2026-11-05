import datetime as dt
from zoneinfo import ZoneInfo
from app.services.garmin_sync import _extract_activity_start
from app.services.insight_dates import is_late_workout

UK_TZ = ZoneInfo("Europe/London")


def test_extract_activity_start_handles_bst_local_time():
    # In July (BST), 18:30 local is 17:30 UTC. If Garmin sends only startTimeLocal="2026-07-15 18:30:00",
    # the extracted start time localized to Europe/London must have hour 18, UTC hour 17, and qualify as late workout.
    payload = {
        "activityId": 12345,
        "startTimeLocal": "2026-07-15 18:30:00",
        "activityType": {"typeKey": "running"},
    }
    start = _extract_activity_start(payload)
    assert start is not None
    assert start.astimezone(UK_TZ).hour == 18
    assert start.astimezone(dt.timezone.utc).hour == 17
    assert is_late_workout(start) is True


def test_extract_activity_start_prefers_gmt_when_available():
    payload = {
        "activityId": 12345,
        "startTimeGMT": "2026-07-15 17:30:00",
        "startTimeLocal": "2026-07-15 18:30:00",
        "activityType": {"typeKey": "running"},
    }
    start = _extract_activity_start(payload)
    assert start is not None
    assert start.astimezone(UK_TZ).hour == 18
    assert start.astimezone(dt.timezone.utc).hour == 17
    assert is_late_workout(start) is True
