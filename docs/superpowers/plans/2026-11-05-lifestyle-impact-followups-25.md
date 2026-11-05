# Lifestyle Impact Follow-ups (#25) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address the seven edge cases and follow-ups from the 4.20.0 review (Issue #25): uncouple sleep and headache roles, fix midnight workout night attribution, correct summer timezone parsing for Garmin workouts, support alternative HRV payload structures, handle un-synced workout periods, and eliminate multi-worker startup races with `IF NOT EXISTS`.

**Architecture:** 
1. Database DDL statements in `backend/app/database.py` are made idempotent with `ADD COLUMN IF NOT EXISTS`.
2. Role updates in `backend/app/routes/activities.py` and `backend/app/services/item_roles.py` are uncoupled so sleep settings never alter `ignore_in_reports` on the headache report.
3. Workout timing in `backend/app/services/insight_dates.py` and `backend/app/services/garmin_sync.py` handles post-midnight workouts (00:00–04:00) as late workouts belonging to the night underway, and correctly localizes local Garmin timestamps in BST.
4. `backend/app/routes/lifestyle_impact.py` extracts HRV from `hrvStatus` payloads and bounds "without workout" candidates to the window where workout data is actually tracked.

**Tech Stack:** FastAPI, SQLAlchemy 2.0+, PostgreSQL 15, Python 3.11/3.14 stdlib (`zoneinfo`, `datetime`), pytest.

**Spec:** Issue #25 and `docs/superpowers/specs/2026-11-02-trustworthy-insights-design.md`.

## Global Constraints

- Work on a dedicated branch (`fix/lifestyle-impact-followups-25`). Never commit to or push `main`. Commit by explicit path.
- Public repository: All tests, fixtures, and documentation must use synthetic data only. No real personal metrics, hostnames, or credentials.
- No new third-party dependencies.
- Standard timezone is `ZoneInfo("Europe/London")`.
- Backend testing: Run tests against a throwaway PostgreSQL container (`TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest tests -q`).

## Review Focus

1. **Multi-worker DDL startup race:** Multiple concurrent backend instances invoking `_ensure_legacy_schema_compatibility()` must not fail with duplicate column errors.
2. **Post-midnight workout edge cases:** A workout at 00:30 BST on Sunday morning must attach to Sunday morning's waking sleep date and be classified as a late workout (`is_late_workout == True`), while an early-morning 05:00 run must belong to Monday morning's waking sleep date and not be late.
3. **British Summer Time (BST) local start time:** When Garmin provides `startTimeLocal` without GMT fields during daylight saving time (e.g. 18:30 in July), it must not be shifted by an hour or stored as UTC.
4. **Role uncoupling:** Setting a role (e.g. habit or reaction) or un-setting a role on Lifestyle Impact must not mutate `Activity.ignore_in_reports`.
5. **Workout sync boundaries:** If workout data has only been synced for the past 14 days of an 84-day window, nights prior to the earliest synced workout must not be falsely treated as "without workout" nights.

---

### Task 1: Idempotent database schema compatibility (`database.py`)

**Files:**
- Modify: `backend/app/database.py:75-180`
- Test: `backend/tests/test_database_startup.py`

**Interfaces:**
- Consumes: PostgreSQL `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` syntax.
- Produces: Race-free `_ensure_legacy_schema_compatibility(engine)` execution across multiple workers.

- [ ] **Step 1: Write the failing test**
Create `backend/tests/test_database_startup.py`:
```python
from sqlalchemy import text
from app.database import _ensure_legacy_schema_compatibility, engine

def test_ensure_legacy_schema_compatibility_is_idempotent(clean_db):
    # Running compatibility twice in succession must not raise ProgrammingError
    _ensure_legacy_schema_compatibility(engine)
    _ensure_legacy_schema_compatibility(engine)
```

- [ ] **Step 2: Run test to verify behavior**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_database_startup.py -v`
Expected: Current code checks `inspector` before adding, but adding `IF NOT EXISTS` directly guards raw DDL execution against concurrent worker races.

- [ ] **Step 3: Update `database.py` with `ADD COLUMN IF NOT EXISTS`**
In `backend/app/database.py`, modify all `ALTER TABLE ... ADD COLUMN` statements inside `_ensure_legacy_schema_compatibility` to include `IF NOT EXISTS`:
- `ALTER TABLE activities ADD COLUMN IF NOT EXISTS is_archived ...`
- `ALTER TABLE activities ADD COLUMN IF NOT EXISTS deprecated_at ...`
- `ALTER TABLE activities ADD COLUMN IF NOT EXISTS ignore_in_reports ...`
- `ALTER TABLE activities ADD COLUMN IF NOT EXISTS report_role ...`
- `ALTER TABLE activities ADD COLUMN IF NOT EXISTS hidden_pages ...`
- `ALTER TABLE activities ADD COLUMN IF NOT EXISTS supports_position ...`
- `ALTER TABLE categories ADD COLUMN IF NOT EXISTS require_rating ...`
- `ALTER TABLE categories ADD COLUMN IF NOT EXISTS rating_label ...`
- `ALTER TABLE categories ADD COLUMN IF NOT EXISTS supports_position ...`
- `ALTER TABLE moods ADD COLUMN IF NOT EXISTS image_url ...`
- `ALTER TABLE moods ADD COLUMN IF NOT EXISTS image_urls ...`
- `ALTER TABLE moods ADD COLUMN IF NOT EXISTS subjective_sleep_rating ...`
- `ALTER TABLE moods ADD COLUMN IF NOT EXISTS weather_temperature_c ...`
- `ALTER TABLE moods ADD COLUMN IF NOT EXISTS weather_condition ...`
- `ALTER TABLE moods ADD COLUMN IF NOT EXISTS weather_cloud_cover ...`

- [ ] **Step 4: Run test to verify it passes**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_database_startup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/database.py backend/tests/test_database_startup.py
git commit -m "fix(db): add IF NOT EXISTS to legacy schema migrations for worker startup safety"
```

---

### Task 2: Uncouple sleep and headache report roles (`activities.py` & `item_roles.py`)

**Files:**
- Modify: `backend/app/routes/activities.py:65-95`
- Modify: `backend/app/services/item_roles.py:28-40`
- Modify: `backend/tests/test_item_roles.py:46-85`

**Interfaces:**
- Consumes: `ActivityReportSettings(report_role, hidden_pages)`
- Produces: Uncoupled `report_role` updating that does not mutate `Activity.ignore_in_reports`.

- [ ] **Step 1: Write the failing tests**
In `backend/tests/test_item_roles.py`:
Update `test_set_role_via_api_also_sets_ignore_flag` to `test_set_role_via_api_does_not_touch_ignore_flag`:
```python
def test_set_role_via_api_does_not_touch_ignore_flag(signed_in, clean_db):
    act = _make_activity(signed_in)
    url = f"/activities/{act['id']}/report-settings"

    # Setting report_role must NOT modify ignore_in_reports
    body = signed_in.put(url, json={"report_role": "habit"}).json()
    assert body["report_role"] == "habit"
    assert body["ignore_in_reports"] is False

    # Setting report_role to None must leave ignore_in_reports as-is
    body = signed_in.put(url, json={"report_role": None}).json()
    assert body["report_role"] is None
    assert body["ignore_in_reports"] is False
```
Update `test_unexcluding_on_headache_page_clears_excluding_role`:
```python
def test_unexcluding_on_headache_page_does_not_touch_report_role(signed_in, clean_db):
    act = _make_activity(signed_in)
    signed_in.put(f"/activities/{act['id']}/report-settings", json={"report_role": "habit"})

    body = signed_in.put(f"/activities/{act['id']}", json={"ignore_in_reports": False}).json()
    assert body["ignore_in_reports"] is False
    assert body["report_role"] == "habit"
```

- [ ] **Step 2: Run tests to verify they fail**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_item_roles.py -k "report_role" -v`
Expected: FAIL (assertion on `ignore_in_reports is False` fails because it was True).

- [ ] **Step 3: Implement uncoupling in `activities.py` and `item_roles.py`**
In `backend/app/routes/activities.py`:
- In `update_activity`: remove lines that clear `act.report_role` when `ignore_in_reports` is modified.
- In `set_report_settings`: remove `act.ignore_in_reports = payload.report_role in EXCLUDING_ROLES`.
In `backend/app/services/item_roles.py`:
- In `effective_role(activity)`: remove fallback `if activity.ignore_in_reports: return "habit"`. Instead, use `activity.report_role` if set; otherwise use the category default.
- In `role_was_set_by_owner(activity)`: return `bool(activity.report_role)`.

- [ ] **Step 4: Run tests to verify they pass**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_item_roles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/routes/activities.py backend/app/services/item_roles.py backend/tests/test_item_roles.py
git commit -m "fix(roles): uncouple lifestyle impact roles from headache report exclusion flag"
```

---

### Task 3: Midnight workouts and late workout classification (`insight_dates.py`)

**Files:**
- Modify: `backend/app/services/insight_dates.py:22-28`
- Modify: `backend/tests/test_insight_dates.py:25-45`

**Interfaces:**
- Consumes: `start_time: dt.datetime` (UTC or tz-aware)
- Produces: 
  - `night_for_workout(start_time: dt.datetime) -> dt.date`
  - `is_late_workout(start_time: dt.datetime) -> bool`

- [ ] **Step 1: Write the failing tests**
In `backend/tests/test_insight_dates.py`, add:
```python
def test_midnight_workout_belongs_to_night_underway():
    # 01:30 BST on Sunday 2026-10-11 attaches to Saturday night's sleep (sleep_date 2026-10-11)
    workout_time = dt.datetime(2026, 10, 11, 0, 30, tzinfo=dt.timezone.utc)
    assert night_for_workout(workout_time) == dt.date(2026, 10, 11)
    assert is_late_workout(workout_time) is True

def test_early_morning_workout_belongs_to_following_night():
    # 05:30 BST on Sunday 2026-10-11 attaches to Sunday night's sleep (sleep_date 2026-10-12)
    workout_time = dt.datetime(2026, 10, 11, 4, 30, tzinfo=dt.timezone.utc)
    assert night_for_workout(workout_time) == dt.date(2026, 10, 12)
    assert is_late_workout(workout_time) is False
```

- [ ] **Step 2: Run tests to verify they fail**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_insight_dates.py -k "workout" -v`
Expected: FAIL (midnight workout returned 2026-10-12 instead of 2026-10-11, and `is_late_workout` was False).

- [ ] **Step 3: Implement updated workout logic in `insight_dates.py`**
```python
def night_for_workout(start_time: dt.datetime) -> dt.date:
    local = start_time.astimezone(UK_TZ)
    day = local.date()
    if local.hour < 4:
        return day
    return day + _ONE_DAY


def is_late_workout(start_time: dt.datetime) -> bool:
    local_hour = start_time.astimezone(UK_TZ).hour
    return local_hour >= 18 or local_hour < 4
```

- [ ] **Step 4: Run tests to verify they pass**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_insight_dates.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/insight_dates.py backend/tests/test_insight_dates.py
git commit -m "fix(insights): attach midnight workouts to current night and classify as late"
```

---

### Task 4: Local timestamp parsing during BST (`garmin_sync.py`)

**Files:**
- Modify: `backend/app/services/garmin_sync.py:145-245`
- Test: `backend/tests/test_garmin_sync.py`

**Interfaces:**
- Consumes: Garmin activity payloads with `startTimeLocal` vs `startTimeGMT`
- Produces: Correctly localized `activity_start: dt.datetime` preserving UK local time.

- [ ] **Step 1: Write the failing test**
In `backend/tests/test_garmin_sync.py` (or new test file):
```python
import datetime as dt
from zoneinfo import ZoneInfo
from app.services.garmin_sync import _extract_activity_start
from app.services.insight_dates import is_late_workout

UK_TZ = ZoneInfo("Europe/London")

def test_extract_activity_start_handles_bst_local_time():
    # In July (BST), 18:30 local is 17:30 UTC. If Garmin only sends startTimeLocal="2026-07-15 18:30:00",
    # the extracted start time in UK_TZ must have hour 18 and qualify as a late workout.
    payload = {
        "activityId": 12345,
        "startTimeLocal": "2026-07-15 18:30:00",
        "activityType": {"typeKey": "running"},
    }
    start = _extract_activity_start(payload)
    assert start is not None
    assert start.astimezone(UK_TZ).hour == 18
    assert is_late_workout(start) is True
```

- [ ] **Step 2: Run test to verify it fails**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_garmin_sync.py -k "bst_local" -v`
Expected: FAIL if `_parse_datetime` blindly assigns UTC to naive local strings.

- [ ] **Step 3: Implement proper local time parsing in `garmin_sync.py`**
In `backend/app/services/garmin_sync.py`:
- Add `_parse_local_datetime(value: Any) -> Optional[dt.datetime]`: Parses ISO/string datetimes without timezone as `Europe/London` (`UK_TZ`), then converts to UTC.
- In `_extract_activity_start`:
  - Check GMT/UTC fields first (`startTimeGMT`, `beginTimestamp`, `startTimeInMillis`, `startTimeInSeconds`) using `_parse_datetime`.
  - For local fields (`startTimeLocal`, `startTime`, `startDate`), parse using `_parse_local_datetime`.

- [ ] **Step 4: Run test to verify it passes**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_garmin_sync.py -k "bst_local" -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/garmin_sync.py backend/tests/test_garmin_sync.py
git commit -m "fix(sync): parse Garmin local workout timestamps with UK timezone during BST"
```

---

### Task 5: HRV payload structure and workout sync boundaries (`lifestyle_impact.py`)

**Files:**
- Modify: `backend/app/routes/lifestyle_impact.py:75-90, 180-205`
- Modify: `backend/tests/test_lifestyle_impact.py`

**Interfaces:**
- Consumes: `GarminHRVDaily.payload` with `hrvStatus`, `GarminActivity` rows.
- Produces: 
  - Extraction of `lastNightAvg` from `hrvStatus` as well as `hrvSummary`.
  - Workout comparison "without" nights bounded by the active workout tracking window.

- [ ] **Step 1: Write the failing tests**
In `backend/tests/test_lifestyle_impact.py`:
```python
def test_hrv_extracts_from_hrv_status_payload(db, clean_db):
    # Garmin payload structure using hrvStatus rather than hrvSummary
    # Verify lifestyle impact extracts lastNightAvg correctly
    ...

def test_workouts_not_falsely_penalized_before_tracking_began(db, clean_db):
    # If activities only exist for the past 14 days, nights prior to the first
    # recorded activity date must not be added to without_nights.
    ...
```

- [ ] **Step 2: Run tests to verify they fail**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_lifestyle_impact.py -k "hrv_status or tracking_began" -v`
Expected: FAIL

- [ ] **Step 3: Implement in `lifestyle_impact.py`**
1. In `overnight_hrv` extraction (around line 79):
```python
if (value := _dig(
    payload,
    ("hrvSummary", "lastNightAvg"),
    ("hrvSummary", "lastNightAverage"),
    ("hrvStatus", "lastNightAvg"),
    ("hrvStatus", "lastNightAverage"),
    ("lastNightAvg",),
    ("lastNightAverage",),
)) is not None:
```
2. In workout candidates construction (around line 195):
- Determine `min_workout_date = db.query(func.min(models.GarminActivity.activity_date)).scalar()` (or earliest in window).
- Only include nights in `all_nights - nights` if the night is `>= min_workout_date + dt.timedelta(days=1)`. If workout tracking had not begun, those earlier nights remain unknown rather than assumed "without workout".

- [ ] **Step 4: Run tests to verify they pass**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests/test_lifestyle_impact.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/routes/lifestyle_impact.py backend/tests/test_lifestyle_impact.py
git commit -m "fix(insights): support hrvStatus payload structure and bound workout comparisons"
```

---

### Task 6: Full verification and regression testing

**Files:**
- Test: Full backend test suite (`backend/tests/`)
- Test: Frontend build & type check (`frontend-web/`)

- [ ] **Step 1: Run complete backend pytest suite**
Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest backend/tests -v`
Expected: 100% tests passing.

- [ ] **Step 2: Run backend code lint**
Run: `cd backend && ruff check --select E4,E7,E9,F app`
Expected: Clean output, 0 errors.

- [ ] **Step 3: Run frontend type checks and build**
Run: `cd frontend-web && npm run check && npm run build`
Expected: 0 errors, build succeeds.

- [ ] **Step 4: Commit and finalize**
Review git diff and confirm all 7 points of #25 are addressed cleanly.
