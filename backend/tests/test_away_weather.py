import datetime as dt

from app import models
from app.services import weather_daily
from app.services.insight_dates import UK_TZ
from app.services.symptom_report import compute_appointment_summary, compute_headache_triggers

LONDON = (51.51, -0.13)
MADRID = (40.42, -3.70)


def _today():
    return dt.datetime.now(UK_TZ).date()


def _hourly(start: dt.date, days: int, pressure: float) -> dict:
    times, pressures, temps = [], [], []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        for hour in range(24):
            times.append(f"{day.isoformat()}T{hour:02d}:00")
            pressures.append(pressure)
            temps.append(20.0)
    return {"hourly": {"time": times, "pressure_msl": pressures, "temperature_2m": temps}}


def test_distance_and_away_threshold():
    assert 1240 < weather_daily.distance_km(*LONDON, *MADRID) < 1280
    home = {"latitude": LONDON[0], "longitude": LONDON[1]}
    assert weather_daily.is_away_from(home, *MADRID) is True
    assert weather_daily.is_away_from(home, 51.60, -0.20) is False  # about 11 km
    assert weather_daily.is_away_from(None, *MADRID) is False


def test_location_is_only_recorded_for_today(clean_db, db):
    today = _today()
    weather_daily.record_location_if_today(db, today - dt.timedelta(days=3), *MADRID)
    weather_daily.record_location_if_today(db, today, None, None)
    assert db.query(models.DayLocation).count() == 0

    weather_daily.record_location_if_today(db, today, 40.41678, -3.70379)
    row = db.query(models.DayLocation).one()
    assert row.location_date == today
    assert (float(row.latitude), float(row.longitude)) == MADRID


def test_saving_an_entry_or_answering_records_todays_location(clean_db, signed_in, db, monkeypatch):
    # Don't call the real weather service for the entry's own weather.
    monkeypatch.setattr("app.routes.mood._fetch_weather_for_timestamp", lambda *a, **k: None)
    now = dt.datetime.now(dt.timezone.utc)
    res = signed_in.post(
        "/mood/",
        json={"mood_score": 2, "timestamp": now.isoformat(), "activity_ids": [], "latitude": MADRID[0], "longitude": MADRID[1]},
    )
    assert res.status_code == 200, res.text
    assert db.query(models.DayLocation).count() == 1

    # Answering for a past day doesn't record where the phone is now.
    old_day = (_today() - dt.timedelta(days=5)).isoformat()
    res = signed_in.put(f"/headache-checks/{old_day}", json={"had_headache": False, "latitude": 1.0, "longitude": 1.0})
    assert res.status_code == 200
    db.expire_all()
    assert db.query(models.DayLocation).count() == 1

    res = signed_in.put(
        f"/headache-checks/{_today().isoformat()}",
        json={"had_headache": False, "latitude": LONDON[0], "longitude": LONDON[1]},
    )
    assert res.status_code == 200
    db.expire_all()
    row = db.query(models.DayLocation).one()
    assert (float(row.latitude), float(row.longitude)) == LONDON


def test_sync_uses_local_weather_for_days_away(clean_db, db, monkeypatch):
    today = dt.date(2026, 10, 20)
    away_day = dt.date(2026, 10, 1)
    calls = []

    def fake_get(url, params):
        calls.append((url, params))
        if (params["latitude"], params["longitude"]) == MADRID:
            day = dt.date.fromisoformat(params["start_date"])
            return _hourly(day, 1, 1030.0)
        if "start_date" in params:
            start = dt.date.fromisoformat(params["start_date"])
            end = dt.date.fromisoformat(params["end_date"])
            return _hourly(start, (end - start).days + 1, 1010.0)
        return _hourly(today - dt.timedelta(days=11), 12, 1010.0)

    monkeypatch.setattr(weather_daily, "_http_get_json", fake_get)
    db.add(models.Mood(timestamp=dt.datetime(2026, 9, 20, 12, tzinfo=dt.timezone.utc)))
    db.add(models.DayLocation(location_date=away_day, latitude=MADRID[0], longitude=MADRID[1]))
    db.add(models.DayLocation(location_date=dt.date(2026, 10, 2), latitude=51.60, longitude=-0.20))  # near home
    db.commit()
    weather_daily.set_home_location(db, *LONDON)

    result = weather_daily.sync_weather(db, today=today)
    assert result["away_days"] == 1

    away = db.query(models.WeatherDaily).filter(models.WeatherDaily.weather_date == away_day).one()
    assert away.is_away is True
    assert float(away.pressure_msl_mean) == 1030.0
    assert (float(away.latitude), float(away.longitude)) == MADRID
    near = db.query(models.WeatherDaily).filter(models.WeatherDaily.weather_date == dt.date(2026, 10, 2)).one()
    assert near.is_away is False
    assert float(near.pressure_msl_mean) == 1010.0

    # A second run doesn't fetch the older away day again.
    calls.clear()
    weather_daily.sync_weather(db, today=today)
    assert not any((p["latitude"], p["longitude"]) == MADRID for _, p in calls)
    assert weather_daily.weather_status(db)["away_days"] == 1


def test_travel_day_is_not_counted_as_a_pressure_change(clean_db, db):
    start = dt.date(2026, 10, 1)
    db.add(models.WeatherDaily(weather_date=start - dt.timedelta(days=1), pressure_msl_mean=1000))
    db.add(models.WeatherDaily(weather_date=start, pressure_msl_mean=1030, is_away=True, latitude=MADRID[0], longitude=MADRID[1]))
    db.add(models.WeatherDaily(weather_date=start + dt.timedelta(days=1), pressure_msl_mean=1028, is_away=True, latitude=MADRID[0], longitude=MADRID[1]))
    db.add(models.WeatherDaily(weather_date=start + dt.timedelta(days=2), pressure_msl_mean=1000))
    db.commit()

    from app.services.symptom_report import _weather_inputs

    inputs = {label: values for values, label, _, _ in _weather_inputs(db, start, start + dt.timedelta(days=2))}
    change = inputs["Air pressure change since yesterday"]
    assert change == {start + dt.timedelta(days=1): -2.0}


def test_timeline_marks_days_away(clean_db, db):
    start = dt.date(2026, 10, 1)
    db.add(models.WeatherDaily(weather_date=start, pressure_msl_mean=1030, is_away=True, latitude=MADRID[0], longitude=MADRID[1]))
    db.add(models.WeatherDaily(weather_date=start + dt.timedelta(days=1), pressure_msl_mean=1010))
    db.commit()
    res = compute_appointment_summary(db, start_date=start, end_date=start + dt.timedelta(days=1))
    assert [d["away"] for d in res["daily_timeline"]] == [True, False]
    # The trigger report still runs with mixed home/away weather.
    assert compute_headache_triggers(db, window="period", start_date=start, end_date=start)["logged_days"] == 0
