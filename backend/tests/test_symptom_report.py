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
    skipped_lunch = models.Activity(name="Skipped Lunch", category_id=cat_gen.id, report_role="possible_cause")
    painkiller = models.Activity(name="Ibuprofen", category_id=cat_gen.id, report_role="reaction")
    db.add_all([headache, alcohol, skipped_lunch, painkiller])
    db.flush()

    # Over 12 days (Oct 2..13):
    # Days Oct 2..7 (6 days): Red Wine on D-1, headache + skipped_lunch + ibuprofen on D
    for d in range(1, 7):
        m_prev = models.Mood(timestamp=dt.datetime(2026, 10, d, 20, 0, tzinfo=dt.timezone.utc))
        m_prev.activities.append(alcohol)
        db.add(m_prev)
        m_curr = models.Mood(timestamp=dt.datetime(2026, 10, d + 1, 14, 0, tzinfo=dt.timezone.utc))
        m_curr.activities.extend([headache, skipped_lunch, painkiller])
        db.add(m_curr)

    # Days Oct 8..13 (6 clean days): logged moods without alcohol/skipped_lunch/headache
    for d in range(7, 14):
        m_clean = models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc))
        db.add(m_clean)

    db.commit()

    res = compute_headache_summary(db, start_date=dt.date(2026, 10, 2), end_date=dt.date(2026, 10, 13))

    day_before_names = [item["activity"] for item in res["triggers_day_before"]]
    same_day_names = [item["activity"] for item in res["triggers_same_day"]]
    left_out = {item["activity"]: item["reason"] for item in res["left_out"]}

    assert "Red Wine" in day_before_names
    assert "Skipped Lunch" in same_day_names
    assert "Ibuprofen" not in day_before_names
    assert "Ibuprofen" not in same_day_names
    assert left_out.get("Ibuprofen") == "reaction"


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


def test_triggers_exclude_unlogged_days_from_baseline(clean_db, db):
    from app.services.symptom_report import compute_headache_triggers

    cat_symp = _get_or_create_category(db, "Headache Issues")
    cat_gen = _get_or_create_category(db, "Daily Activities")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    wine = models.Activity(name="Red Wine", category_id=cat_gen.id)
    db.add_all([headache, wine])
    db.flush()

    # Window Oct 2..Oct 31 (30 calendar days), but user only logs on 12 days:
    # Oct 1..6: wine logged; Oct 2..7: headache logged (6 days with wine day-before)
    # Oct 7..12: logged without wine; Oct 8..13: clean logged days (6 days without wine day-before)
    # Oct 14..31: completely blank (18 unlogged days)
    for d in range(1, 7):
        m = models.Mood(timestamp=dt.datetime(2026, 10, d, 20, 0, tzinfo=dt.timezone.utc))
        m.activities.append(wine)
        db.add(m)
    for d in range(2, 8):
        m = models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc))
        m.activities.append(headache)
        db.add(m)
    for d in range(7, 14):
        db.add(models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc), mood_score=8))
    db.commit()

    res = compute_headache_triggers(
        db, window="period", start_date=dt.date(2026, 10, 2), end_date=dt.date(2026, 10, 31)
    )
    assert res["logged_days"] == 12
    assert res["symptom_days"] == 6
    assert res["clean_days"] == 6
    wine_item = next(item for item in res["triggers_day_before"] if item["activity"] == "Red Wine")
    assert wine_item["with_nights"] == 6
    assert wine_item["without_nights"] == 6


def test_before_sleep_never_appears_in_same_day_even_after_midnight(clean_db, db):
    from app.services.symptom_report import compute_headache_triggers

    cat_symp = _get_or_create_category(db, "Headache Issues")
    cat_sleep = _get_or_create_category(db, "Before Sleep")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    magnesium = models.Activity(name="Magnesium", category_id=cat_sleep.id)
    db.add_all([headache, magnesium])
    db.flush()

    # 12 days (Oct 2..13):
    # Days 2..7: Before Sleep Magnesium logged at 00:30 UTC (after midnight) + headache at 14:00 same morning
    for d in range(2, 8):
        m_bs = models.Mood(timestamp=dt.datetime(2026, 10, d, 0, 30, tzinfo=dt.timezone.utc))
        m_bs.activities.append(magnesium)
        db.add(m_bs)
        m_h = models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc))
        m_h.activities.append(headache)
        db.add(m_h)
    # Days 1 and 7..13: logged clean entries so day-before exposure baseline exists
    db.add(models.Mood(timestamp=dt.datetime(2026, 10, 1, 14, 0, tzinfo=dt.timezone.utc)))
    for d in range(8, 14):
        db.add(models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc)))
    db.commit()

    res = compute_headache_triggers(
        db, window="period", start_date=dt.date(2026, 10, 2), end_date=dt.date(2026, 10, 13)
    )
    assert any(i["activity"] == "Magnesium" for i in res["triggers_day_before"])
    assert all(i["activity"] != "Magnesium" for i in res["triggers_same_day"])
    assert all(i.get("activity") != "Magnesium" for i in res["no_clear_link"])


def test_weak_and_zero_effects_go_to_no_clear_link_and_verdict_looks_random(clean_db, db):
    from app.services.symptom_report import compute_headache_triggers

    cat_symp = _get_or_create_category(db, "Headache Issues")
    cat_gen = _get_or_create_category(db, "Daily Activities")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    coffee = models.Activity(name="Coffee", category_id=cat_gen.id)
    db.add_all([headache, coffee])
    db.flush()

    # 20 days (Oct 2..21): 10 symptom days, 10 clean days.
    # Coffee logged equally before/on half the symptom days and half the clean days -> 0% effect.
    db.add(models.Mood(timestamp=dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc)))
    for idx in range(20):
        day = dt.date(2026, 10, 2) + dt.timedelta(days=idx)
        m = models.Mood(timestamp=dt.datetime.combine(day, dt.time(12, 0), tzinfo=dt.timezone.utc))
        if idx % 2 == 0:
            m.activities.append(headache)
        if idx % 4 in (0, 1):
            m.activities.append(coffee)
        db.add(m)
    db.commit()

    res = compute_headache_triggers(
        db, window="period", start_date=dt.date(2026, 10, 2), end_date=dt.date(2026, 10, 21)
    )
    assert res["triggers_day_before"] == []
    assert res["triggers_same_day"] == []
    assert res["clue_count"] == 0
    assert res["tested_count"] >= 1
    assert res["verdict_kind"] == "looks_random"
    coffee_entries = [item for item in res["no_clear_link"] if item.get("activity") == "Coffee"]
    assert len(coffee_entries) == 1  # deduplicated across day_before & same_day


def test_clue_suppressed_from_no_clear_link_and_too_early_deduplicated(clean_db, db):
    from app.services.symptom_report import compute_headache_triggers

    cat_symp = _get_or_create_category(db, "Headache Issues")
    cat_gen = _get_or_create_category(db, "Daily Activities")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    wine = models.Activity(name="Red Wine", category_id=cat_gen.id)
    rare = models.Activity(name="Sauna", category_id=cat_gen.id)
    db.add_all([headache, wine, rare])
    db.flush()

    # Oct 1..6: Wine; Oct 2..7: Headache (strong day-before clue; weak/different same-day)
    # Oct 7..13: clean days; Sauna logged only 3 times
    for d in range(1, 7):
        m = models.Mood(timestamp=dt.datetime(2026, 10, d, 20, 0, tzinfo=dt.timezone.utc))
        m.activities.append(wine)
        db.add(m)
    for d in range(2, 8):
        m = models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc))
        m.activities.append(headache)
        if d <= 4:
            m.activities.append(rare)
        db.add(m)
    for d in range(8, 14):
        db.add(models.Mood(timestamp=dt.datetime(2026, 10, d, 14, 0, tzinfo=dt.timezone.utc)))
    db.commit()

    res = compute_headache_triggers(
        db, window="period", start_date=dt.date(2026, 10, 2), end_date=dt.date(2026, 10, 13)
    )
    assert any(i["activity"] == "Red Wine" for i in res["triggers_day_before"])
    assert all(i.get("activity") != "Red Wine" for i in res["no_clear_link"])
    assert all(i.get("activity") != "Red Wine" for i in res["too_early"])
    sauna_early = [i for i in res["too_early"] if i["activity"] == "Sauna"]
    assert len(sauna_early) == 1


def test_biometrics_hrv_paths_stress_fallback_and_negligible_filter(clean_db, db):
    from app.services.symptom_report import compute_headache_triggers

    cat_symp = _get_or_create_category(db, "Headache Issues")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    db.add(headache)
    db.flush()

    # 12 days (Oct 1..12): 6 symptom, 6 clean
    for d in range(1, 13):
        curr = dt.date(2026, 10, d)
        prev = curr - dt.timedelta(days=1)
        m = models.Mood(timestamp=dt.datetime.combine(curr, dt.time(12, 0), tzinfo=dt.timezone.utc))
        if d <= 6:
            m.activities.append(headache)
            hrv_val = 30
            stress_prev = 65
        else:
            hrv_val = 65
            stress_prev = 25
        db.add(m)
        # HRV using "lastNight" path (not in old 4-path list)
        db.add(models.GarminHRVDaily(hrv_date=curr, payload={"hrvSummary": {"lastNight": hrv_val}}))
        # Stress daily on day before (no avgSleepStress in GarminSleepDaily)
        db.add(models.GarminStressDaily(stress_date=prev, overall_stress_level=stress_prev))
        # Sleep score identical on all days (0 diff -> should go to no_clear_link, not biometrics clues)
        db.add(models.GarminSleepDaily(sleep_date=curr, sleep_score=75, payload={}))
    db.commit()

    res = compute_headache_triggers(
        db, window="period", start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 12)
    )
    clue_metrics = {b["metric"]: b for b in res["biometrics"]}
    assert "Overnight HRV (night before)" in clue_metrics
    assert "Daytime Stress (day before)" in clue_metrics
    assert "Overnight Stress (night before)" not in clue_metrics
    assert "Sleep Score (night before)" not in clue_metrics
    assert any(
        item.get("kind") == "biometric" and item.get("metric") == "Sleep Score (night before)"
        for item in res["no_clear_link"]
    )


def test_garmin_midnight_workout_uses_night_for_workout(clean_db, db):
    from app.services.symptom_report import compute_headache_triggers

    cat_symp = _get_or_create_category(db, "Headache Issues")
    headache = models.Activity(name="Headache", category_id=cat_symp.id)
    db.add(headache)
    db.flush()

    # 12 days (Oct 1..12):
    # Days 1..6: workout at 00:30 UTC on day D (which night_for_workout maps to day D, NOT D+1) + headache on day D
    # Days 7..12: clean days without workouts
    for d in range(1, 13):
        curr = dt.date(2026, 10, d)
        m = models.Mood(timestamp=dt.datetime.combine(curr, dt.time(12, 0), tzinfo=dt.timezone.utc))
        if d <= 6:
            m.activities.append(headache)
            db.add(
                models.GarminActivity(
                    garmin_activity_id=f"mid-{d}",
                    activity_date=curr,
                    start_time=dt.datetime.combine(curr, dt.time(0, 30), tzinfo=dt.timezone.utc),
                    duration_seconds=1800,
                )
            )
        db.add(m)
    db.commit()

    res = compute_headache_triggers(
        db, window="period", start_date=dt.date(2026, 10, 1), end_date=dt.date(2026, 10, 12)
    )
    workout = next((i for i in res["triggers_day_before"] if i["activity"] == "Workout (day before)"), None)
    assert workout is not None
    assert workout["effect"] == 100  # all 6 midnight workouts aligned with days 1..6 (not shifted to 2..7)


def test_triggers_windows_and_empty_db(clean_db, db):
    from app.services.symptom_report import compute_headache_triggers

    empty_all = compute_headache_triggers(db, window="all")
    assert empty_all["verdict_kind"] == "insufficient_data"
    assert empty_all["logged_days"] == 0
    assert empty_all["triggers_day_before"] == []

    empty_90 = compute_headache_triggers(db, window="90d")
    assert empty_90["window"] == "90d"
    assert empty_90["verdict_kind"] == "insufficient_data"


