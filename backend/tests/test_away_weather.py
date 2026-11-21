import datetime as dt

from app import models
from app.services import weather_daily
from app.services.insight_dates import UK_TZ
from app.services.symptom_report import compute_appointment_summary

LONDON = (51.51, -0.13)
NEAR_LONDON = (51.60, -0.05)  # about 11 km away: still "home"
MADRID = (40.42, -3.70)
TODAY = dt.date(2026, 10, 20)


def _set_home(db, position=LONDON):
    weather_daily.set_home_location(db, *position)


def _hourly_for(day: dt.date, pressure: float, temp: float = 20.0) -> dict:
    times = [f"{day.isoformat()}T{h:02d}:00" for h in range(24)]
    return {"hourly": {"time": times, "pressure_msl": [pressure] * 24, "temperature_2m": [temp] * 24}}


# --- Recording where you were -------------------------------------------------


def test_record_day_location_only_today_or_yesterday_and_rounds(clean_db, db):
    assert weather_daily.record_day_location(db, TODAY, 40.41678, -3.70379, today=TODAY) is not None
    assert weather_daily.record_day_location(db, TODAY - dt.timedelta(days=1), *MADRID, today=TODAY) is not None
    # An older day being filled in later must not get today's position.
    assert weather_daily.record_day_location(db, TODAY - dt.timedelta(days=2), *MADRID, today=TODAY) is None
    # Missing or impossible positions are ignored.
    assert weather_daily.record_day_location(db, TODAY, None, None, today=TODAY) is None
    assert weather_daily.record_day_location(db, TODAY, 123.0, 0.0, today=TODAY) is None
    assert weather_daily.record_day_location(db, TODAY, float("nan"), 0.0, today=TODAY) is None
    db.commit()

    row = db.query(models.DayLocation).filter(models.DayLocation.location_date == TODAY).one()
    assert (float(row.latitude), float(row.longitude)) == (40.42, -3.70)
    assert db.query(models.DayLocation).count() == 2


def test_new_position_for_the_day_clears_its_fetched_weather(clean_db, db):
    row = weather_daily.record_day_location(db, TODAY, *MADRID, today=TODAY)
    row.pressure_msl_mean = 1000
    row.weather_fetched_at = dt.datetime.now(dt.timezone.utc)
    db.commit()

    weather_daily.record_day_location(db, TODAY, *MADRID, today=TODAY)  # same place: kept
    assert row.weather_fetched_at is not None

    weather_daily.record_day_location(db, TODAY, 41.39, 2.17, today=TODAY)  # moved on to Barcelona
    db.commit()
    assert (float(row.latitude), float(row.longitude)) == (41.39, 2.17)
    assert row.pressure_msl_mean is None
    assert row.weather_fetched_at is None


def test_saving_an_entry_or_check_records_todays_location(clean_db, signed_in, db):
    now = dt.datetime.now(UK_TZ)
    today = now.date()
    old = now - dt.timedelta(days=5)

    res = signed_in.post(
        "/mood/", json={"timestamp": now.isoformat(), "mood_score": 3, "latitude": MADRID[0], "longitude": MADRID[1]}
    )
    assert res.status_code == 200
    res = signed_in.post(
        "/mood/", json={"timestamp": old.isoformat(), "mood_score": 3, "latitude": MADRID[0], "longitude": MADRID[1]}
    )
    assert res.status_code == 200
    days = {d for (d,) in db.query(models.DayLocation.location_date)}
    assert days == {today}

    yesterday = today - dt.timedelta(days=1)
    res = signed_in.put(
        f"/headache-checks/{yesterday.isoformat()}",
        json={"had_headache": False, "latitude": MADRID[0], "longitude": MADRID[1]},
    )
    assert res.status_code == 200
    db.expire_all()
    days = {d for (d,) in db.query(models.DayLocation.location_date)}
    assert days == {today, yesterday}

    bad = signed_in.put(
        f"/headache-checks/{today.isoformat()}", json={"had_headache": False, "latitude": 95, "longitude": 0}
    )
    assert bad.status_code == 422


# --- Fetching weather for days away ---------------------------------------------


def test_sync_away_weather_fetches_only_finished_days_away(clean_db, db, monkeypatch):
    calls = []

    def fake_get(url, params):
        calls.append((url, params))
        return _hourly_for(dt.date.fromisoformat(params["start_date"]), pressure=1001.0, temp=28.0)

    monkeypatch.setattr(weather_daily, "_http_get_json", fake_get)
    assert weather_daily.sync_away_weather(db, today=TODAY)["status"] == "no_home_location"

    _set_home(db)
    recent_away = TODAY - dt.timedelta(days=2)
    old_away = TODAY - dt.timedelta(days=40)
    near_home = TODAY - dt.timedelta(days=3)
    for day, pos in ((recent_away, MADRID), (old_away, MADRID), (near_home, NEAR_LONDON), (TODAY, MADRID)):
        db.add(models.DayLocation(location_date=day, latitude=pos[0], longitude=pos[1]))
    db.commit()

    result = weather_daily.sync_away_weather(db, today=TODAY)
    assert result == {"status": "ok", "stored": 2}
    fetched = {params["start_date"]: url for url, params in calls}
    # Today isn't finished; the nearby day uses home weather.
    assert fetched == {
        recent_away.isoformat(): weather_daily.FORECAST_URL,
        old_away.isoformat(): weather_daily.ARCHIVE_URL,
    }
    assert all((p["latitude"], p["longitude"]) == MADRID for _, p in calls)

    row = db.query(models.DayLocation).filter(models.DayLocation.location_date == recent_away).one()
    assert float(row.pressure_msl_mean) == 1001.0
    assert float(row.temperature_max_c) == 28.0

    calls.clear()
    weather_daily.sync_away_weather(db, today=TODAY)
    assert calls == []


def test_sync_away_weather_retries_after_a_failed_fetch(clean_db, db, monkeypatch):
    def failing_get(url, params):
        raise OSError("network down")

    monkeypatch.setattr(weather_daily, "_http_get_json", failing_get)
    _set_home(db)
    day = TODAY - dt.timedelta(days=1)
    db.add(models.DayLocation(location_date=day, latitude=MADRID[0], longitude=MADRID[1]))
    db.commit()

    assert weather_daily.sync_away_weather(db, today=TODAY) == {"status": "ok", "stored": 0}
    row = db.query(models.DayLocation).one()
    assert row.weather_fetched_at is None


def test_sync_away_weather_is_throttled(clean_db, db, monkeypatch):
    calls = []
    monkeypatch.setattr(
        weather_daily,
        "_http_get_json",
        lambda url, params: calls.append(params) or _hourly_for(dt.date.fromisoformat(params["start_date"]), 1000.0),
    )
    _set_home(db)
    for i in range(1, weather_daily.MAX_AWAY_FETCHES_PER_RUN + 6):
        db.add(
            models.DayLocation(location_date=TODAY - dt.timedelta(days=i), latitude=MADRID[0], longitude=MADRID[1])
        )
    db.commit()

    weather_daily.sync_away_weather(db, today=TODAY)
    assert len(calls) == weather_daily.MAX_AWAY_FETCHES_PER_RUN


# --- Using it in the report --------------------------------------------------------


def test_weather_for_report_swaps_in_away_weather(clean_db, db):
    _set_home(db)
    days = [TODAY - dt.timedelta(days=i) for i in range(4, 0, -1)]
    for day in days:
        db.add(models.WeatherDaily(weather_date=day, pressure_msl_mean=1020, temperature_max_c=12))
    fetched_at = dt.datetime.now(dt.timezone.utc)
    # days[1]: away and fetched; days[2]: away, not fetched yet; days[3]: near home.
    db.add(
        models.DayLocation(
            location_date=days[1],
            latitude=MADRID[0],
            longitude=MADRID[1],
            pressure_msl_mean=1008,
            temperature_max_c=29,
            weather_fetched_at=fetched_at,
        )
    )
    db.add(models.DayLocation(location_date=days[2], latitude=MADRID[0], longitude=MADRID[1]))
    db.add(models.DayLocation(location_date=days[3], latitude=NEAR_LONDON[0], longitude=NEAR_LONDON[1]))
    db.commit()

    weather, away = weather_daily.weather_for_report(db, days[0], days[-1])
    assert away == {days[1], days[2]}
    assert weather[days[0]] == {"pressure": 1020.0, "temp_max": 12.0}
    assert weather[days[1]] == {"pressure": 1008.0, "temp_max": 29.0}
    assert days[2] not in weather  # unknown until fetched, rather than wrongly using home
    assert weather[days[3]] == {"pressure": 1020.0, "temp_max": 12.0}


def test_no_home_area_means_no_away_days(clean_db, db):
    db.add(models.DayLocation(location_date=TODAY, latitude=MADRID[0], longitude=MADRID[1]))
    db.commit()
    assert weather_daily.away_days(db, TODAY, TODAY) == set()


def test_timeline_marks_away_days(clean_db, db):
    _set_home(db)
    away_day = dt.date(2026, 10, 2)
    db.add(models.DayLocation(location_date=away_day, latitude=MADRID[0], longitude=MADRID[1]))
    db.add(models.DayLocation(location_date=dt.date(2026, 10, 3), latitude=NEAR_LONDON[0], longitude=NEAR_LONDON[1]))
    db.commit()

    res = compute_appointment_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 3))
    flags = {d["date"]: d["away"] for d in res["daily_timeline"]}
    assert flags == {"2026-10-01": False, "2026-10-02": True, "2026-10-03": False}


def test_distance_km_is_sensible():
    assert round(weather_daily.distance_km(*LONDON, *MADRID)) in range(1250, 1275)
    assert weather_daily.distance_km(*LONDON, *LONDON) == 0
