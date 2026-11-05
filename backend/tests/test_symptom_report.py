import datetime as dt
import pytest
from app import models
from app.services.symptom_report import compute_headache_summary


def _get_or_create_category(db, name):
    cat = db.query(models.Category).filter(models.Category.name == name).first()
    if not cat:
        cat = models.Category(name=name)
        db.add(cat)
        db.flush()
    return cat


def test_symptom_days_and_frequency_and_severity(clean_db, db):
    cat_symp = _get_or_create_category(db, "Headache Issues")

    migraine = models.Activity(name="Migraine", category_id=cat_symp.id, report_role="symptom")
    db.add(migraine)
    db.flush()

    # Day 1: symptom day with severity 3
    m1 = models.Mood(timestamp=dt.datetime(2026, 10, 10, 14, 0, tzinfo=dt.timezone.utc), mood_score=5)
    db.add(m1)
    db.flush()
    db.add(models.MoodActivityDetail(mood_id=m1.id, activity_id=migraine.id, severity=3))
    m1.activities.append(migraine)

    # Day 2: clean day
    m2 = models.Mood(timestamp=dt.datetime(2026, 10, 11, 14, 0, tzinfo=dt.timezone.utc), mood_score=8)
    db.add(m2)
    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 10), end_date=dt.date(2026, 10, 11))
    assert res["total_days"] == 2
    assert res["symptom_days"] == 1
    assert res["clean_days"] == 1
    assert res["frequency"] == 50
    assert res["average_severity"] == 3.0


def test_day_before_and_same_day_separation(clean_db, db):
    cat_gen = _get_or_create_category(db, "Daily Activities")
    cat_symp = _get_or_create_category(db, "Headache Issues")

    headache = models.Activity(name="Headache", category_id=cat_symp.id, report_role="symptom")
    alcohol = models.Activity(name="Red Wine", category_id=cat_gen.id, report_role="possible_cause")
    painkiller = models.Activity(name="Ibuprofen", category_id=cat_gen.id, report_role="reaction")
    db.add_all([headache, alcohol, painkiller])
    db.flush()

    # Over 10 days:
    # Days 1..5: Wine on day D-1, headache on day D, Ibuprofen on day D
    for d in range(1, 6):
        date_prev = dt.date(2026, 10, d)
        date_curr = dt.date(2026, 10, d + 1)
        # Prev day alcohol
        m_prev = models.Mood(timestamp=dt.datetime(2026, 10, d, 20, 0, tzinfo=dt.timezone.utc))
        m_prev.activities.append(alcohol)
        db.add(m_prev)
        # Curr day headache & ibuprofen
        m_curr = models.Mood(timestamp=dt.datetime(2026, 10, d + 1, 14, 0, tzinfo=dt.timezone.utc))
        m_curr.activities.extend([headache, painkiller])
        db.add(m_curr)

    # Days 6..10: clean days without wine
    for d in range(6, 12):
        m_clean = models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc))
        db.add(m_clean)

    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 2), end_date=dt.date(2026, 10, 11))

    # Alcohol should be in day_before triggers, NOT same_day
    day_before_names = [item["activity"] for item in res["triggers_day_before"]]
    same_day_names = [item["activity"] for item in res["triggers_same_day"]]

    assert "Red Wine" in day_before_names
    assert "Red Wine" not in same_day_names
    # Ibuprofen should be in same_day, NOT day_before
    assert "Ibuprofen" in same_day_names
    assert "Ibuprofen" not in day_before_names


def test_hydration_missing_or_zero_means_unknown(clean_db, db):
    cat_symp = _get_or_create_category(db, "Headache Issues")
    headache = models.Activity(name="Cluster Headache", category_id=cat_symp.id, report_role="symptom")
    db.add(headache)
    db.flush()

    # 12 days of data
    for d in range(1, 13):
        target_date = dt.date(2026, 10, d)
        if d <= 6:
            m = models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc))
            m.activities.append(headache)
            db.add(m)
        else:
            m = models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc))
            db.add(m)

        # Hydration on d-1: day 1 has 0 ml (should be ignored), days 2..6 have 1200ml (50% goal), days 7..12 have 2400ml (100% goal)
        prev_date = target_date - dt.timedelta(days=1)
        if d == 1:
            db.add(models.GarminHydrationDaily(hydration_date=prev_date, consumed_ml=0, goal_ml=2400))
        elif d <= 6:
            db.add(models.GarminHydrationDaily(hydration_date=prev_date, consumed_ml=1200, goal_ml=2400))
        else:
            db.add(models.GarminHydrationDaily(hydration_date=prev_date, consumed_ml=2400, goal_ml=2400))

    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 12))
    hydration_bio = next((b for b in res["biometrics"] if "Hydration" in b["metric"]), None)
    assert hydration_bio is not None
    # 0 ml record on day 1 was excluded, so symptom days with valid hydration is 5, clean days is 6
    assert hydration_bio["symptom_avg"] == 50.0
    assert hydration_bio["clean_avg"] == 100.0
    assert hydration_bio["effect"] == -50.0


def test_garmin_workouts_day_before(clean_db, db):
    cat_symp = _get_or_create_category(db, "Headache Issues")
    headache = models.Activity(name="Tension Headache", category_id=cat_symp.id, report_role="symptom")
    db.add(headache)
    db.flush()

    # 12 days
    for d in range(1, 13):
        curr_date = dt.date(2026, 10, d)
        prev_date = curr_date - dt.timedelta(days=1)
        if d <= 6:
            # Symptom day following workout
            m = models.Mood(timestamp=dt.datetime.combine(curr_date, dt.time(12, 0), tzinfo=dt.timezone.utc))
            m.activities.append(headache)
            db.add(m)
            db.add(models.GarminActivity(
                garmin_activity_id=f"act-{d}",
                activity_date=prev_date,
                start_time=dt.datetime.combine(prev_date, dt.time(19, 0), tzinfo=dt.timezone.utc),  # late workout
                duration_seconds=3600  # long workout (> 45m)
            ))
        else:
            # Clean day without workout
            m = models.Mood(timestamp=dt.datetime.combine(curr_date, dt.time(12, 0), tzinfo=dt.timezone.utc))
            db.add(m)

    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 12))
    day_before_names = [item["activity"] for item in res["triggers_day_before"]]
    assert "Workout (day before)" in day_before_names
    assert "Late workout (after 6pm, day before)" in day_before_names


def test_hidden_and_habit_left_out(clean_db, db):
    cat_gen = _get_or_create_category(db, "Misc")

    earplugs = models.Activity(name="Earplugs", category_id=cat_gen.id, hidden_pages=["acupuncture_report"])
    eyemask = models.Activity(name="Eye Mask", category_id=cat_gen.id, report_role="habit")
    db.add_all([earplugs, eyemask])
    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 10))
    left_out = {item["activity"]: item["reason"] for item in res["left_out"]}
    assert left_out.get("Earplugs") == "hidden"
    assert left_out.get("Eye Mask") == "habit"
