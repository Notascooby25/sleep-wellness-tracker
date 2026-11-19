import datetime as dt
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


def test_category_default_describes_night_not_in_left_out(clean_db, db):
    cat_morning = _get_or_create_category(db, "Morning / Waking Feedback")
    cat_gen = _get_or_create_category(db, "Misc")

    # Item with default category role (describes_night) but no owner override
    woke_tired = models.Activity(name="Woke up tired", category_id=cat_morning.id, report_role=None)
    # Item with explicit owner role
    explicit_desc = models.Activity(name="Restless", category_id=cat_gen.id, report_role="describes_night")
    db.add_all([woke_tired, explicit_desc])
    db.flush()

    # Log woke_tired on day 1 so it appears in the analysed window
    m = models.Mood(timestamp=dt.datetime(2026, 10, 2, 8, 0, tzinfo=dt.timezone.utc), mood_score=6)
    db.add(m)
    db.flush()
    m.activities.append(woke_tired)
    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 10))
    left_out = {item["activity"]: item["reason"] for item in res["left_out"]}

    # Default category item should NOT be in left_out
    assert "Woke up tired" not in left_out
    # Explicit owner override item SHOULD be in left_out
    assert left_out.get("Restless") == "describes_night"

    # When owner clears report_role on explicit item, it disappears from left_out
    explicit_desc.report_role = None
    db.commit()
    res2 = compute_headache_summary(db, start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 10))
    left_out2 = {item["activity"]: item["reason"] for item in res2["left_out"]}
    assert "Restless" not in left_out2


def test_appointment_summary_breakdowns_hide_zeros_and_fold_deprecated(clean_db, db):
    from app.services.symptom_report import compute_appointment_summary

    cat_symp = _get_or_create_category(db, "Headache Issues")
    headache_old = models.Activity(
        name="Headache",
        category_id=cat_symp.id,
        deprecated_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )
    headache_cur = models.Activity(name="Headache", category_id=cat_symp.id)
    migraine = models.Activity(name="Migraine", category_id=cat_symp.id)
    unlogged = models.Activity(name="Sinus Pressure", category_id=cat_symp.id)
    db.add_all([headache_old, headache_cur, migraine, unlogged])
    db.flush()

    # Day 1: two mood entries — Headache logged twice, Migraine once, positions Left & Forehead
    m1a = models.Mood(timestamp=dt.datetime(2026, 10, 10, 9, 0, tzinfo=dt.timezone.utc))
    m1a.activities.append(headache_cur)
    db.add(m1a)
    db.flush()
    db.add(models.MoodActivityDetail(mood_id=m1a.id, activity_id=headache_cur.id, position='["Left","Forehead"]'))

    m1b = models.Mood(timestamp=dt.datetime(2026, 10, 10, 16, 0, tzinfo=dt.timezone.utc))
    m1b.activities.extend([headache_cur, migraine])
    db.add(m1b)
    db.flush()
    db.add(models.MoodActivityDetail(mood_id=m1b.id, activity_id=migraine.id, position='["Left"]'))

    # Day 2: deprecated Headache with plain-string position
    m2 = models.Mood(timestamp=dt.datetime(2026, 10, 11, 14, 0, tzinfo=dt.timezone.utc))
    m2.activities.append(headache_old)
    db.add(m2)
    db.flush()
    db.add(models.MoodActivityDetail(mood_id=m2.id, activity_id=headache_old.id, position="Left"))

    # Day 3: clean day
    db.add(models.Mood(timestamp=dt.datetime(2026, 10, 12, 14, 0, tzinfo=dt.timezone.utc), mood_score=8))
    db.commit()

    res = compute_appointment_summary(db, start_date=dt.date(2026, 10, 10), end_date=dt.date(2026, 10, 12))
    assert res["total_days"] == 3
    assert res["symptom_days"] == 2
    assert res["clean_days"] == 1
    assert res["frequency"] == 67

    assert res["symptom_breakdown"] == [
        {"activity_id": headache_cur.id, "activity": "Headache", "days": 2, "is_migraine": False},
        {"activity_id": migraine.id, "activity": "Migraine", "days": 1, "is_migraine": True},
    ]
    assert res["position_breakdown"] == [
        {"position": "Left", "days": 2},
        {"position": "Forehead", "days": 1},
    ]
    assert res["daily_timeline"] == [
        {
            "date": "2026-10-10",
            "status": "migraine",
            "symptoms": ["Headache", "Migraine"],
            "positions": ["Forehead", "Left"],
            "has_acupuncture": False,
        },
        {
            "date": "2026-10-11",
            "status": "headache",
            "symptoms": ["Headache"],
            "positions": ["Left"],
            "has_acupuncture": False,
        },
        {
            "date": "2026-10-12",
            "status": "clear",
            "symptoms": [],
            "positions": [],
            "has_acupuncture": False,
        },
    ]


def test_appointment_summary_severity_ignores_entries_outside_window(clean_db, db):
    from app.services.symptom_report import compute_appointment_summary

    cat_symp = _get_or_create_category(db, "Headache Issues")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    db.add(headache)
    db.flush()

    m_before = models.Mood(timestamp=dt.datetime(2026, 10, 9, 14, 0, tzinfo=dt.timezone.utc))
    m_before.activities.append(headache)
    db.add(m_before)
    db.flush()
    db.add(models.MoodActivityDetail(mood_id=m_before.id, activity_id=headache.id, severity=5))

    m_in = models.Mood(timestamp=dt.datetime(2026, 10, 10, 14, 0, tzinfo=dt.timezone.utc))
    m_in.activities.append(headache)
    db.add(m_in)
    db.flush()
    db.add(models.MoodActivityDetail(mood_id=m_in.id, activity_id=headache.id, severity=2))
    db.commit()

    res = compute_appointment_summary(db, start_date=dt.date(2026, 10, 10), end_date=dt.date(2026, 10, 12))
    assert res["average_severity"] == 2.0


def test_appointment_summary_prior_period_rules(clean_db, db):
    from app.services.symptom_report import compute_appointment_summary

    cat_symp = _get_or_create_category(db, "Headache Issues")
    cat_gen = _get_or_create_category(db, "Appointments")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    acupuncture = models.Activity(name="Acupuncture", category_id=cat_gen.id)
    db.add_all([headache, acupuncture])
    db.flush()

    # Sessions on Oct 1 and Oct 10
    for day in (1, 10):
        m = models.Mood(timestamp=dt.datetime(2026, 10, day, 12, 0, tzinfo=dt.timezone.utc))
        m.activities.append(acupuncture)
        db.add(m)

    # Prior session gap Oct 2..Oct 10 (9 days): 3 headache days -> 33%
    for day in (3, 5, 7):
        m = models.Mood(timestamp=dt.datetime(2026, 10, day, 12, 0, tzinfo=dt.timezone.utc))
        m.activities.append(headache)
        db.add(m)

    # Current session gap Oct 11..Oct 20 (10 days): 2 headache days -> 20%
    for day in (12, 18):
        m = models.Mood(timestamp=dt.datetime(2026, 10, day, 12, 0, tzinfo=dt.timezone.utc))
        m.activities.append(headache)
        db.add(m)
    db.commit()

    # 1) Viewing since latest session (Oct 11..Oct 20) -> compares to previous session gap Oct 2..Oct 10
    res = compute_appointment_summary(db, start_date=dt.date(2026, 10, 11), end_date=dt.date(2026, 10, 20))
    assert res["previous_period"] == {
        "start_date": "2026-10-02",
        "end_date": "2026-10-10",
        "total_days": 9,
        "symptom_days": 3,
        "frequency": 33,
        "comparison_type": "previous_session_gap",
    }

    # 2) Multi-session span (Oct 2..Oct 20, contains Oct 10 inside [start, end)) -> equal-length prior (Sep 13..Oct 1)
    # Oct 1 has a logged mood (Acupuncture) with 0 headaches -> frequency 0, NOT None
    res_span = compute_appointment_summary(db, start_date=dt.date(2026, 10, 2), end_date=dt.date(2026, 10, 20))
    assert res_span["previous_period"] == {
        "start_date": "2026-09-13",
        "end_date": "2026-10-01",
        "total_days": 19,
        "symptom_days": 0,
        "frequency": 0,
        "comparison_type": "equal_length_prior",
    }
    assert any(d["date"] == "2026-10-10" and d["has_acupuncture"] for d in res_span["daily_timeline"])

    # 3) Period whose prior window has zero logged moods -> previous_period is None
    res_early = compute_appointment_summary(db, start_date=dt.date(2026, 9, 15), end_date=dt.date(2026, 9, 20))
    assert res_early["previous_period"] is None


def test_acupuncture_sessions_uk_bst_and_empty_db_summary(clean_db, db):
    from app.services.symptom_report import compute_appointment_summary, get_acupuncture_session_dates

    # Empty DB first
    empty = compute_appointment_summary(db, start_date=dt.date(2026, 7, 1), end_date=dt.date(2026, 7, 3))
    assert empty["symptom_days"] == 0
    assert empty["frequency"] == 0
    assert empty["previous_period"] is None
    assert empty["symptom_breakdown"] == []
    assert empty["position_breakdown"] == []
    assert len(empty["daily_timeline"]) == 3
    assert all(d["status"] == "clear" for d in empty["daily_timeline"])

    # Acupuncture logged at 23:30 UTC in July (BST = UTC+1 -> 00:30 on July 11 UK time)
    cat = _get_or_create_category(db, "Appointments")
    acu = models.Activity(name="Acupuncture Session", category_id=cat.id)
    db.add(acu)
    db.flush()
    m = models.Mood(timestamp=dt.datetime(2026, 7, 10, 23, 30, tzinfo=dt.timezone.utc))
    m.activities.append(acu)
    db.add(m)
    db.commit()

    assert get_acupuncture_session_dates(db) == [dt.date(2026, 7, 11)]

