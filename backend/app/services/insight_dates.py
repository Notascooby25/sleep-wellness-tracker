"""Match logged entries and workouts to the night they affect.

Nights are keyed by Garmin's sleep date, which is the morning you wake up.
"""

import datetime as dt
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")
_ONE_DAY = dt.timedelta(days=1)


def night_for_entry(logged_at: dt.datetime, before_sleep: bool) -> dt.date:
    local = logged_at.astimezone(UK_TZ)
    day = local.date()
    # Before Sleep items logged in the small hours or next morning belong to the evening before.
    if before_sleep and local.hour < 12:
        day -= _ONE_DAY
    return day + _ONE_DAY


def night_for_workout(start_time: dt.datetime) -> dt.date:
    return start_time.astimezone(UK_TZ).date() + _ONE_DAY


def is_late_workout(start_time: dt.datetime) -> bool:
    return start_time.astimezone(UK_TZ).hour >= 18
