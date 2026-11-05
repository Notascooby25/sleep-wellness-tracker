"""Which night's sleep a logged entry or workout is compared with."""

import datetime as dt

from app.services.insight_dates import is_late_workout, night_for_entry, night_for_workout

UTC = dt.timezone.utc


def at(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=UTC)


def test_bedtime_entry_goes_to_following_night():
    assert night_for_entry(at(2026, 10, 9, 21, 30), before_sleep=True) == dt.date(2026, 10, 10)


def test_after_midnight_in_summer_time_still_previous_evening():
    # 23:30 UTC is 00:30 BST on Saturday.
    assert night_for_entry(at(2026, 10, 9, 23, 30), before_sleep=True) == dt.date(2026, 10, 10)


def test_before_sleep_logged_next_morning_counts_as_previous_evening():
    assert night_for_entry(at(2026, 11, 7, 9), before_sleep=True) == dt.date(2026, 11, 7)


def test_daytime_item_goes_to_that_nights_sleep():
    assert night_for_entry(at(2026, 11, 7, 9), before_sleep=False) == dt.date(2026, 11, 8)


def test_workouts():
    evening = at(2026, 10, 12, 17, 30)  # 18:30 BST
    assert night_for_workout(evening) == dt.date(2026, 10, 13)
    assert is_late_workout(evening) is True
    assert is_late_workout(at(2026, 10, 12, 16, 30)) is False


def test_midnight_workout_belongs_to_night_underway():
    # 01:30 BST on Sunday 2026-10-11 (00:30 UTC) belongs to Saturday night's sleep (sleep_date 2026-10-11)
    workout_time = at(2026, 10, 11, 0, 30)
    assert night_for_workout(workout_time) == dt.date(2026, 10, 11)
    assert is_late_workout(workout_time) is True


def test_early_morning_workout_belongs_to_following_night():
    # 05:30 BST on Sunday 2026-10-11 (04:30 UTC) belongs to Sunday night's sleep (sleep_date 2026-10-12)
    workout_time = at(2026, 10, 11, 4, 30)
    assert night_for_workout(workout_time) == dt.date(2026, 10, 12)
    assert is_late_workout(workout_time) is False
