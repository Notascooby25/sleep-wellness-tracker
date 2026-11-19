import datetime as dt
from app import models


def test_headache_summary_endpoint_structure(clean_db, signed_in, db):
    # Setup some test data
    cat = models.Category(name="Headache Issues")
    db.add(cat)
    db.flush()
    migraine = models.Activity(name="Migraine", category_id=cat.id, report_role="symptom")
    db.add(migraine)
    db.commit()

    res = signed_in.get("/reports/headache-summary?start_date=2026-10-01&end_date=2026-10-10")
    assert res.status_code == 200
    data = res.json()

    assert "triggers_day_before" in data
    assert "triggers_same_day" in data
    assert "biometrics" in data
    assert "left_out" in data
    assert "too_early" in data
    assert "triggers" in data  # legacy alias
    assert data["total_days"] == 10
    assert data["symptom_days"] == 0


def test_appointment_summary_endpoint_and_bad_range(clean_db, signed_in, db):
    cat = models.Category(name="Headache Issues")
    db.add(cat)
    db.flush()
    headache = models.Activity(name="Headache", category_id=cat.id)
    db.add(headache)
    db.flush()
    m = models.Mood(timestamp=dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.timezone.utc))
    m.activities.append(headache)
    db.add(m)
    db.commit()

    res = signed_in.get("/reports/headache-appointment-summary?start_date=2026-10-01&end_date=2026-10-10")
    assert res.status_code == 200
    data = res.json()
    assert data["total_days"] == 10
    assert data["symptom_days"] == 1
    assert data["frequency"] == 10
    assert data["previous_period"] is None
    assert data["symptom_breakdown"] == [
        {"activity_id": headache.id, "activity": "Headache", "days": 1, "is_migraine": False}
    ]
    assert data["position_breakdown"] == []
    assert len(data["daily_timeline"]) == 10

    bad = signed_in.get("/reports/headache-appointment-summary?start_date=2026-10-12&end_date=2026-10-10")
    assert bad.status_code == 400


def test_headache_triggers_endpoint_windows_and_validation(clean_db, signed_in, db):
    for window in ("90d", "all"):
        res = signed_in.get(f"/reports/headache-triggers?window={window}")
        assert res.status_code == 200
        body = res.json()
        assert body["window"] == window
        assert body["verdict_kind"] == "insufficient_data"
        assert "no_clear_link" in body
        assert "triggers_day_before" in body
        assert "biometrics" in body
        assert "too_early" in body
        assert "left_out" in body

    period_res = signed_in.get(
        "/reports/headache-triggers?window=period&start_date=2026-10-01&end_date=2026-10-10"
    )
    assert period_res.status_code == 200
    assert period_res.json()["window"] == "period"

    bad_window = signed_in.get("/reports/headache-triggers?window=foo")
    assert bad_window.status_code == 400

    bad_range = signed_in.get(
        "/reports/headache-triggers?window=period&start_date=2026-10-12&end_date=2026-10-10"
    )
    assert bad_range.status_code == 400

    bad_legacy = signed_in.get("/reports/headache-summary?start_date=2026-10-12&end_date=2026-10-10")
    assert bad_legacy.status_code == 400


def test_acupuncture_sessions_endpoint_uses_uk_timezone(clean_db, signed_in, db):
    cat = models.Category(name="Appointments")
    db.add(cat)
    db.flush()
    acu = models.Activity(name="Acupuncture", category_id=cat.id)
    db.add(acu)
    db.flush()
    # 2026-07-10 23:30 UTC is 2026-07-11 00:30 BST
    m = models.Mood(timestamp=dt.datetime(2026, 7, 10, 23, 30, tzinfo=dt.timezone.utc))
    m.activities.append(acu)
    db.add(m)
    db.commit()

    res = signed_in.get("/reports/acupuncture-sessions")
    assert res.status_code == 200
    assert res.json() == {"sessions": ["2026-07-11"]}

