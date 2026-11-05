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
