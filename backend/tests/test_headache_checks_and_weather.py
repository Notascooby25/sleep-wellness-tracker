import datetime as dt

from app import models
from app.services import weather_daily
from app.services.symptom_report import (
    _difference_from_usual,
    compute_appointment_summary,
    compute_headache_triggers,
)


def _category(db, name):
    cat = db.query(models.Category).filter(models.Category.name == name).first()
    if not cat:
        cat = models.Category(name=name)
        db.add(cat)
        db.flush()
    return cat


def _activity(db, name, category, role=None):
    act = models.Activity(name=name, category_id=_category(db, category).id, report_role=role)
    db.add(act)
    db.flush()
    return act


def _mood(db, when, *activities):
    mood = models.Mood(timestamp=when)
    mood.activities.extend(activities)
    db.add(mood)
    return mood


def _utc(day, hour=12, minute=0):
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt.timezone.utc)


# --- Daily check API -------------------------------------------------------


def test_headache_check_save_read_and_clear(clean_db, signed_in, db):
    headache = _activity(db, "Headache", "Headache Issues")
    _mood(db, _utc(dt.date(2026, 10, 5)), headache)
    db.commit()

    empty = signed_in.get("/headache-checks/2026-10-05")
    assert empty.status_code == 200
    assert empty.json() == {
        "date": "2026-10-05",
        "answered": False,
        "had_headache": None,
        "onset": None,
        "logged_symptoms": ["Headache"],
    }

    saved = signed_in.put("/headache-checks/2026-10-05", json={"had_headache": True, "onset": "afternoon"})
    assert saved.status_code == 200
    assert saved.json()["answered"] is True
    assert saved.json()["onset"] == "afternoon"

    # Answering "no" drops any start time.
    changed = signed_in.put("/headache-checks/2026-10-05", json={"had_headache": False, "onset": "morning"})
    assert changed.json()["had_headache"] is False
    assert changed.json()["onset"] is None
    assert db.query(models.HeadacheCheck).count() == 1

    listed = signed_in.get("/headache-checks?start_date=2026-10-01&end_date=2026-10-31")
    assert listed.status_code == 200
    assert [row["date"] for row in listed.json()] == ["2026-10-05"]

    bad = signed_in.put("/headache-checks/2026-10-05", json={"had_headache": True, "onset": "lunch"})
    assert bad.status_code == 400

    cleared = signed_in.delete("/headache-checks/2026-10-05")
    assert cleared.status_code == 200
    assert cleared.json()["answered"] is False
    assert db.query(models.HeadacheCheck).count() == 0


def test_headache_check_list_rejects_bad_range(clean_db, signed_in):
    res = signed_in.get("/headache-checks?start_date=2026-10-10&end_date=2026-10-01")
    assert res.status_code == 400


# --- The answer decides the day ---------------------------------------------


def test_answer_overrides_tapped_items_in_summary(clean_db, db):
    brain_fog = _activity(db, "Brain Fog", "Headache Issues")
    # Oct 1: brain fog tapped, but answered "no headache" -> clear.
    _mood(db, _utc(dt.date(2026, 10, 1)), brain_fog)
    db.add(models.HeadacheCheck(check_date=dt.date(2026, 10, 1), had_headache=False))
    # Oct 2: nothing tapped, but answered "yes, woke with it" -> headache.
    db.add(models.HeadacheCheck(check_date=dt.date(2026, 10, 2), had_headache=True, onset="woke"))
    db.commit()

    res = compute_appointment_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 3))
    assert res["symptom_days"] == 1
    assert res["confirmed_days"] == 2
    timeline = {d["date"]: d for d in res["daily_timeline"]}
    assert timeline["2026-10-01"]["status"] == "clear"
    assert timeline["2026-10-01"]["confirmed"] is True
    assert timeline["2026-10-02"]["status"] == "headache"
    assert timeline["2026-10-02"]["onset"] == "woke"
    assert timeline["2026-10-03"]["confirmed"] is False


def test_answer_only_days_count_as_logged_in_triggers(clean_db, db):
    start = dt.date(2026, 10, 1)
    for i in range(4):
        db.add(models.HeadacheCheck(check_date=start + dt.timedelta(days=i), had_headache=i % 2 == 0))
    db.commit()

    res = compute_headache_triggers(db, window="period", start_date=start, end_date=start + dt.timedelta(days=3))
    assert res["logged_days"] == 4
    assert res["confirmed_days"] == 4
    assert res["symptom_days"] == 2
    assert res["clean_days"] == 2


def _onset_scenario(db, onset):
    """Coffee logged at 15:00 UK on 6 headache days, never on 6 clear days."""
    headache = _activity(db, "Headache", "Headache Issues")
    coffee = _activity(db, "Coffee", "Lifestyle", role="possible_cause")
    start = dt.date(2026, 10, 1)
    for i in range(12):
        day = start + dt.timedelta(days=i)
        if i < 6:
            _mood(db, _utc(day, 14), coffee)  # 14:00 UTC = 15:00 UK (BST)
            _mood(db, _utc(day, 19), headache)
            db.add(models.HeadacheCheck(check_date=day, had_headache=True, onset=onset))
        else:
            _mood(db, _utc(day, 14))
            db.add(models.HeadacheCheck(check_date=day, had_headache=False))
    db.commit()
    return compute_headache_triggers(db, window="period", start_date=start, end_date=start + dt.timedelta(days=11))


def test_items_logged_after_the_headache_started_are_not_causes(clean_db, db):
    res = _onset_scenario(db, "morning")
    same_day = [t["activity"] for t in res["triggers_same_day"]]
    assert "Coffee" not in same_day


def test_items_logged_before_the_headache_started_still_count(clean_db, db):
    res = _onset_scenario(db, "evening")
    same_day = [t["activity"] for t in res["triggers_same_day"]]
    assert "Coffee" in same_day


# --- New measures -------------------------------------------------------------


def test_difference_from_usual_needs_enough_earlier_nights():
    start = dt.date(2026, 10, 1)
    times = {start + dt.timedelta(days=i): 23 * 60 for i in range(6)}
    times[start + dt.timedelta(days=6)] = 24 * 60 + 30  # 00:30, 90 minutes late
    result = _difference_from_usual(times, start, start + dt.timedelta(days=6))
    assert start not in result  # no earlier nights yet
    assert result[start + dt.timedelta(days=5)] == 0.0
    assert result[start + dt.timedelta(days=6)] == 90.0


def test_falling_air_pressure_shows_up_as_a_weather_clue(clean_db, db):
    start = dt.date(2026, 10, 1)
    pressure = 1020.0
    db.add(models.WeatherDaily(weather_date=start - dt.timedelta(days=1), pressure_msl_mean=pressure))
    for i in range(20):
        day = start + dt.timedelta(days=i)
        headache_day = i % 2 == 0
        # Pressure falls sharply into each headache day and recovers into each clear day.
        pressure += -12.0 - (i % 3) if headache_day else 12.0 + (i % 3)
        db.add(models.WeatherDaily(weather_date=day, pressure_msl_mean=pressure, temperature_max_c=15))
        db.add(models.HeadacheCheck(check_date=day, had_headache=headache_day))
    db.commit()

    res = compute_headache_triggers(db, window="period", start_date=start, end_date=start + dt.timedelta(days=19))
    found = {b["metric"]: b for b in res["biometrics"]}
    assert "Air pressure change since yesterday" in found
    clue = found["Air pressure change since yesterday"]
    assert clue["source"] == "weather"
    assert clue["symptom_avg"] < 0 < clue["clean_avg"]
    assert clue["better"] is False


def test_new_garmin_measures_are_tested(clean_db, db):
    start = dt.date(2026, 10, 1)
    for i in range(20):
        day = start + dt.timedelta(days=i)
        headache_day = i % 2 == 0
        db.add(
            models.GarminSleepDaily(
                sleep_date=day,
                total_sleep_minutes=300 + (i % 3) if headache_day else 480 + (i % 3),
                body_battery_wakeup=30 + (i % 3) if headache_day else 80 + (i % 3),
            )
        )
        db.add(models.HeadacheCheck(check_date=day, had_headache=headache_day))
    db.commit()

    res = compute_headache_triggers(db, window="period", start_date=start, end_date=start + dt.timedelta(days=19))
    found = {b["metric"]: b for b in res["biometrics"]}
    assert found["Sleep length (night before)"]["unit"] == "h"
    assert found["Sleep length (night before)"]["symptom_avg"] < found["Sleep length (night before)"]["clean_avg"]
    assert found["Body Battery on waking"]["symptom_avg"] < found["Body Battery on waking"]["clean_avg"]


# --- Weather fetching ---------------------------------------------------------


def _fake_hourly(start: dt.date, days: int, pressure: float = 1015.0) -> dict:
    times, pressures, temps = [], [], []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        for hour in range(24):
            times.append(f"{day.isoformat()}T{hour:02d}:00")
            pressures.append(pressure + d)
            temps.append(10.0 + hour / 2)
    return {"hourly": {"time": times, "pressure_msl": pressures, "temperature_2m": temps}}


def test_daily_from_hourly_averages_each_day():
    days = weather_daily.daily_from_hourly(_fake_hourly(dt.date(2026, 10, 1), 2))
    assert days[dt.date(2026, 10, 1)] == {
        "pressure_msl_mean": 1015.0,
        "temperature_max_c": 21.5,
        "temperature_min_c": 10.0,
    }
    assert days[dt.date(2026, 10, 2)]["pressure_msl_mean"] == 1016.0


def test_daily_from_hourly_skips_mostly_missing_days():
    payload = _fake_hourly(dt.date(2026, 10, 1), 1)
    payload["hourly"]["pressure_msl"] = [None] * 20 + [1000.0] * 4
    days = weather_daily.daily_from_hourly(payload)
    assert days[dt.date(2026, 10, 1)]["pressure_msl_mean"] is None


def test_sync_weather_fills_history_and_recent_days(clean_db, db, monkeypatch):
    calls = []

    def fake_get(url, params):
        calls.append((url, params))
        if url == weather_daily.ARCHIVE_URL:
            start = dt.date.fromisoformat(params["start_date"])
            end = dt.date.fromisoformat(params["end_date"])
            return _fake_hourly(start, (end - start).days + 1)
        return _fake_hourly(dt.date(2026, 10, 20) - dt.timedelta(days=11), 12)

    monkeypatch.setattr(weather_daily, "_http_get_json", fake_get)
    today = dt.date(2026, 10, 20)

    assert weather_daily.sync_weather(db, today=today)["status"] == "no_home_location"

    _mood(db, _utc(dt.date(2026, 9, 1)))
    db.commit()
    weather_daily.set_home_location(db, 51.50731, -0.12765)
    assert calls == []
    result = weather_daily.sync_weather(db, today=today)
    assert result["status"] == "ok"
    assert all(params["latitude"] == 51.51 and params["longitude"] == -0.13 for _, params in calls)

    stored = {d for (d,) in db.query(models.WeatherDaily.weather_date)}
    assert min(stored) == dt.date(2026, 8, 31)
    assert max(stored) == dt.date(2026, 10, 19)  # today is incomplete, so not stored
    assert len(stored) == (dt.date(2026, 10, 19) - dt.date(2026, 8, 31)).days + 1

    # A second run only refreshes the recent days.
    calls.clear()
    weather_daily.sync_weather(db, today=today)
    assert [url for url, _ in calls] == [weather_daily.FORECAST_URL]


def test_home_location_route_rounds_and_resets_on_move(clean_db, signed_in, db, monkeypatch):
    monkeypatch.setattr(weather_daily, "_http_get_json", lambda url, params: {"hourly": {}})

    assert signed_in.post("/weather/sync").status_code == 400

    res = signed_in.put("/weather/home-location", json={"latitude": 51.50731, "longitude": -0.12765})
    assert res.status_code == 200
    assert res.json()["home_location"] == {"latitude": 51.51, "longitude": -0.13}

    db.add(models.WeatherDaily(weather_date=dt.date(2026, 10, 1), pressure_msl_mean=1010))
    db.commit()
    # Same area again keeps stored weather.
    signed_in.put("/weather/home-location", json={"latitude": 51.509, "longitude": -0.131})
    assert db.query(models.WeatherDaily).count() == 1
    # A different area starts again.
    signed_in.put("/weather/home-location", json={"latitude": 53.48, "longitude": -2.24})
    db.expire_all()
    assert db.query(models.WeatherDaily).count() == 0

    status = signed_in.get("/weather/status")
    assert status.status_code == 200
    assert status.json()["home_location_set"] is True

    assert signed_in.put("/weather/home-location", json={"latitude": 123, "longitude": 0}).status_code == 422
