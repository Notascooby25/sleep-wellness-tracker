"""Lifestyle Impact: made-up nights in November 2026 (UK time equals UTC then)."""

import datetime as dt

import pytest

from app import models

END = dt.date(2026, 11, 30)
UTC = dt.timezone.utc


def d(day: int) -> dt.date:
    """Evening `day` of the scenario; day 1 is 4 Nov so every night falls in the 28-day window."""
    return dt.date(2026, 11, 3) + dt.timedelta(days=day)


class World:
    def __init__(self, db):
        self.db = db
        self.categories: dict[str, models.Category] = {}
        self.activities: dict[str, models.Activity] = {}

    def item(self, name, category="Before Sleep", **fields):
        if category not in self.categories:
            self.categories[category] = models.Category(name=category)
            self.db.add(self.categories[category])
        act = models.Activity(name=name, category=self.categories[category], **fields)
        self.db.add(act)
        self.activities[name] = act
        return act

    def log(self, day: dt.date, names, hour=21):
        acts = [self.activities[n] if n in self.activities else self.item(n) for n in names]
        stamp = dt.datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
        self.db.add(models.Mood(timestamp=stamp, activities=acts))

    def sleep(self, night: dt.date, score=None, payload=None):
        self.db.add(models.GarminSleepDaily(sleep_date=night, sleep_score=score, payload=payload))

    def done(self):
        self.db.commit()


def impact(client, metric="sleep_score", days=28):
    response = client.get(f"/lifestyle-impact?metric={metric}&days={days}&end_date={END.isoformat()}")
    assert response.status_code == 200, response.text
    return response.json()


def names(rows):
    return [row["activity"] for row in rows]


def find(rows, name):
    return next(row for row in rows if row["activity"] == name)


@pytest.fixture
def world(clean_db, db):
    return World(db)


def test_evening_item_matched_to_following_night(signed_in, world):
    # Alcohol on even evenings. The old code compared it with the night before, which scored 85.
    for day in range(1, 21):
        world.log(d(day), ["Alcohol"] if day % 2 == 0 else ["Reading"])
        world.sleep(d(day + 1), 60 if day % 2 == 0 else 85)
    world.done()

    alcohol = find(impact(signed_in)["items"], "Alcohol")
    assert alcohol["effect"] < 0
    assert alcohol["better"] is False
    assert alcohol["with_nights"] == 10
    assert alcohol["without_nights"] == 10


def test_unlogged_evening_is_not_a_without_night(signed_in, world):
    for day in range(1, 13):
        world.log(d(day), ["Alcohol"] if day <= 6 else ["Reading"])
        world.sleep(d(day + 1), 60 if day <= 6 else 80)
    for day in range(13, 23):
        world.sleep(d(day + 1), 80)
    world.done()

    alcohol = find(impact(signed_in)["items"], "Alcohol")
    assert alcohol["without_nights"] == 6


def test_night_items_and_habits_left_out(signed_in, world):
    world.item("Woke During Night", category="During Sleep")
    world.item("Meditation", report_role="habit")
    world.item("Old exclusion", ignore_in_reports=True)
    world.item("Hidden here", hidden_pages=["lifestyle_impact"])
    for day in range(1, 21):
        world.log(d(day), ["Meditation", "Old exclusion", "Hidden here"] if day % 2 else ["Reading"])
        world.log(d(day + 1), ["Woke During Night"], hour=7)
        world.sleep(d(day + 1), 60 if day % 2 else 80)
    world.done()

    body = impact(signed_in)
    shown = names(body["items"]) + names(body["too_early"])
    for name in ("Woke During Night", "Meditation", "Old exclusion", "Hidden here"):
        assert name not in shown
    reasons = {row["activity"]: row["reason"] for row in body["left_out"]}
    assert reasons == {"Meditation": "habit", "Old exclusion": "habit", "Hidden here": "hidden"}


def test_too_early_group(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Caffeine"] if day <= 3 else ["Reading"])
        world.sleep(d(day + 1), 70 + day % 3)
    world.done()

    early = find(impact(signed_in)["too_early"], "Caffeine")
    assert early["with_nights"] == 3


def test_confidence_before_size(signed_in, world):
    # Wild is in another tab, so its noisy nights don't count as Steady's "without" nights.
    world.item("Wild", category="Lifestyle")
    world.item("Walk", category="Lifestyle")
    wild = [40, 95, 45, 90, 42]
    for day in range(1, 26):
        if day <= 10:
            world.log(d(day), ["Steady"])
            score = 75
        elif day <= 15:
            world.log(d(day), ["Wild"])
            score = wild[day - 11]
        else:
            world.log(d(day), ["Reading", "Walk"] if day <= 20 else ["Reading"])
            score = 72
        world.sleep(d(day + 1), score)
    world.done()

    items = impact(signed_in)["items"]
    order = names(items)
    assert find(items, "Steady")["confidence"] == "strong"
    assert find(items, "Wild")["confidence"] != "strong"
    assert abs(find(items, "Wild")["effect"]) > abs(find(items, "Steady")["effect"])
    assert order.index("Steady") < order.index("Wild")


def test_negligible_effect_dropped(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Bland"] if day % 2 else ["Reading"])
        world.sleep(d(day + 1), 70 + ((day + 1) // 2) % 4)
    world.done()

    body = impact(signed_in)
    assert "Bland" not in names(body["items"])


def test_hrv_uses_last_night(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Alcohol"] if day % 2 == 0 else ["Reading"])
        last_night = 50 if day % 2 == 0 else 80
        world.db.add(models.GarminHRVDaily(
            hrv_date=d(day + 1), weekly_avg=70, payload={"hrvSummary": {"lastNightAvg": last_night}}
        ))
    world.done()

    alcohol = find(impact(signed_in, metric="overnight_hrv")["items"], "Alcohol")
    assert alcohol["effect"] == pytest.approx(-30)


def test_stress_uses_sleep_stress(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Alcohol"] if day % 2 == 0 else ["Reading"])
        world.sleep(d(day + 1), 70, payload={"dailySleepDTO": {"avgSleepStress": 40.0 if day % 2 == 0 else 20.0}})
    world.done()

    body = impact(signed_in, metric="overnight_stress")
    assert body["metric_label"] == "Overnight stress"
    alcohol = find(body["items"], "Alcohol")
    assert alcohol["effect"] == pytest.approx(20)
    assert alcohol["better"] is False


def test_stress_falls_back_to_all_day(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Alcohol"] if day % 2 == 0 else ["Reading"])
        world.sleep(d(day + 1), 70)
        world.db.add(models.GarminStressDaily(stress_date=d(day + 1), overall_stress_level=45 if day % 2 == 0 else 25))
    world.done()

    body = impact(signed_in, metric="overnight_stress")
    assert body["metric_label"] == "Stress"
    assert find(body["items"], "Alcohol")["effect"] == pytest.approx(20)


def test_steps_use_next_day(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Late night"] if day % 2 == 0 else ["Reading"])
        world.db.add(models.GarminStepsDaily(steps_date=d(day + 1), total_steps=4000 if day % 2 == 0 else 9000))
    world.db.add(models.GarminStepsDaily(steps_date=d(1), total_steps=None))
    world.done()

    late = find(impact(signed_in, metric="steps")["items"], "Late night")
    assert late["effect"] == -5000


def test_workouts_included(signed_in, world):
    for day in range(1, 21):
        world.sleep(d(day + 1), 60 if day <= 6 else 80)
    for day in range(1, 7):
        hour = 19 if day <= 3 else 8
        world.db.add(models.GarminActivity(
            garmin_activity_id=f"w{day}", activity_date=d(day),
            start_time=dt.datetime.combine(d(day), dt.time(hour), tzinfo=UTC), duration_seconds=1800,
        ))
    world.done()

    body = impact(signed_in)
    workout = find(body["items"], "Workout")
    assert workout["activity_id"] is None
    assert workout["with_nights"] == 6
    assert find(body["too_early"], "Late workout (after 6pm)")["with_nights"] == 3


def test_missing_fields_and_empty_period(signed_in, world):
    world.sleep(d(5), None)
    world.db.add(models.GarminHRVDaily(hrv_date=d(5), weekly_avg=70, payload={"hrvSummary": {}}))
    world.done()

    for metric in ("sleep_score", "overnight_hrv", "overnight_stress", "resting_heart_rate", "steps"):
        body = impact(signed_in, metric=metric)
        assert body["items"] == [] and body["too_early"] == []
        assert body["avg_value"] is None


def test_same_item_twice_counts_once(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Alcohol"] if day % 2 == 0 else ["Reading"])
        if day % 2 == 0:
            world.log(d(day), ["Alcohol"], hour=22)
        world.sleep(d(day + 1), 60 if day % 2 == 0 else 85)
    world.done()

    assert find(impact(signed_in)["items"], "Alcohol")["with_nights"] == 10


def test_seven_days_rejected(signed_in, clean_db):
    assert signed_in.get("/lifestyle-impact?metric=sleep_score&days=7").status_code == 422


def test_twins_flagged(signed_in, world):
    for day in range(1, 21):
        world.log(d(day), ["Cold", "Bathroom"] if day % 2 == 0 else ["Reading"])
        world.sleep(d(day + 1), 60 if day % 2 == 0 else 85)
    world.done()

    items = impact(signed_in)["items"]
    assert find(items, "Cold")["logged_with"] == ["Bathroom"]
    assert find(items, "Bathroom")["logged_with"] == ["Cold"]
