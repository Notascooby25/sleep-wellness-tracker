# Headache Report on Shared Comparison Method (#26) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the trigger and biometric analysis on the Acupuncture & Symptom Report page onto the shared comparison method in `backend/app/services/` (item roles, night matching, permutation with/without comparison, multiple-testing correction), with day-before and same-day trigger lists, Garmin hydration and workout triggers, symptom role classification, and unified Lifestyle Impact row UI.

**Architecture:**
1. Database startup migration sets `report_role = 'symptom'` for existing activities matching headache/migraine/jaw or under the "Headache Issues" category.
2. A new service module `backend/app/services/symptom_report.py` identifies symptom days from activities with `effective_role == 'symptom'`, runs permutation with/without comparisons via `comparison.py` for day-before triggers, same-day causes/reactions, Garmin workouts, and Garmin biometrics (including hydration % of goal with missing treated as unknown).
3. `backend/app/routes/reports.py` serves the updated `/reports/headache-summary` schema.
4. `frontend-web/src/routes/acupuncture-report/+page.svelte` renders the timeframe controls and summary cards, followed by the two trigger lists and biometrics using the established "Quiet Sanctuary" token styling, confidence bars, ⋯ role menus, and "Left out of this page" chips.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, SvelteKit, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-11-02-trustworthy-insights-design.md` (Stage 2: Headache report)

## Global Constraints

- Never commit secrets, real personal health figures, hostnames, or IPs to the public repository.
- Changes reach `main` only through PRs merged on GitHub, never committed directly to `main`.
- Real PostgreSQL test database required for backend testing (`TEST_DATABASE_URL=... pytest tests -v`).
- Follow the "Quiet Sanctuary" design tokens in `frontend-web/src/tokens.css` and `DESIGN.md`.
- Keep timeframe controls, acupuncture session picker, and summary cards intact.
- Hydration 0 ml or no record means unknown, not zero; compare by % of daily goal using logged days only.

## Review Focus

1. **Days with multiple symptoms or severities:** When multiple symptom entries exist on the same day, day is counted once as a symptom day, and all recorded numeric severities are averaged.
2. **Missing hydration logs:** Days with 0 ml consumed or null are excluded from hydration comparison rather than counted as 0% goal.
3. **Role menu on acupuncture report:** Toggling "Hide from this page only" adds `acupuncture_report` to `hidden_pages` without touching `lifestyle_impact` or `ignore_in_reports`.
4. **Day-before vs same-day boundary:** Evening / Before Sleep items logged in early morning belong to the night before; daytime activities logged on symptom day belong to same day.
5. **Multiple testing correction:** Applying Benjamini-Hochberg across all candidate triggers so testing many activities does not yield false positives.

---

### Task 1: Database Startup Migration & Symptom Role Helper

**Files:**
- Modify: `backend/app/database.py:108-115`
- Modify: `backend/app/services/item_roles.py:5-41`
- Test: `backend/tests/test_symptom_roles.py`

**Interfaces:**
- Produces: `item_roles.is_symptom(activity: models.Activity) -> bool`
- Consumes: `models.Activity.report_role`, `models.Category.name`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_symptom_roles.py
import pytest
from app import models
from app.services import item_roles


def test_is_symptom_from_explicit_role():
    act = models.Activity(name="Custom Pain", report_role="symptom")
    assert item_roles.is_symptom(act) is True


def test_is_symptom_from_headache_category():
    cat = models.Category(name="Headache Issues")
    act = models.Activity(name="Sharp Tension", category=cat)
    assert item_roles.is_symptom(act) is True


def test_is_symptom_false_for_cause():
    cat = models.Category(name="Food / Drink")
    act = models.Activity(name="Coffee", category=cat)
    assert item_roles.is_symptom(act) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_symptom_roles.py -v`
Expected: FAIL with `AttributeError: module 'app.services.item_roles' has no attribute 'is_symptom'`

- [ ] **Step 3: Implement `is_symptom` and startup migration**

Add `is_symptom` to `backend/app/services/item_roles.py`:
```python
ACUPUNCTURE_PAGE = "acupuncture_report"

def is_symptom(activity: models.Activity) -> bool:
    return effective_role(activity) == "symptom"
```

In `backend/app/database.py`, add the SQL update inside `_ensure_legacy_schema_compatibility`:
```python
        if inspector.has_table("activities"):
            conn.execute(
                text("""
                    UPDATE activities
                    SET report_role = 'symptom'
                    WHERE report_role IS NULL
                      AND (
                        LOWER(name) LIKE '%headache%'
                        OR LOWER(name) LIKE '%migraine%'
                        OR LOWER(name) LIKE '%jaw%'
                        OR category_id IN (
                            SELECT id FROM categories WHERE LOWER(TRIM(name)) = 'headache issues'
                        )
                      )
                """)
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_symptom_roles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/app/services/item_roles.py backend/tests/test_symptom_roles.py
git commit -m "feat(reports): add symptom role classification and startup migration"
```

---

### Task 2: Symptom Report Computation Service

**Files:**
- Create: `backend/app/services/symptom_report.py`
- Test: `backend/tests/test_symptom_report.py`

**Interfaces:**
- Produces: `symptom_report.compute_headache_summary(db: Session, start_date: dt.date | None, end_date: dt.date | None) -> dict`
- Consumes: `comparison.compare`, `comparison.bh_adjust`, `comparison.level_for`, `insight_dates.night_for_entry`, `insight_dates.is_late_workout`, `item_roles.is_symptom`, `item_roles.effective_role`, `item_roles.is_hidden_on`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_symptom_report.py
import datetime as dt
import pytest
from app import models
from app.services.symptom_report import compute_headache_summary


def test_symptom_days_and_severity(db_session):
    cat_symp = models.Category(name="Headache Issues")
    db_session.add(cat_symp)
    db_session.flush()

    migraine = models.Activity(name="Migraine", category_id=cat_symp.id, report_role="symptom")
    db_session.add(migraine)
    db_session.flush()

    # Day 1 with symptom and severity 3
    m1 = models.Mood(timestamp=dt.datetime(2026, 10, 10, 10, 0, tzinfo=dt.timezone.utc), mood_score=5)
    db_session.add(m1)
    db_session.flush()
    db_session.add(models.MoodActivityDetail(mood_id=m1.id, activity_id=migraine.id, severity=3))
    m1.activities.append(migraine)

    # Day 2 clean
    m2 = models.Mood(timestamp=dt.datetime(2026, 10, 11, 10, 0, tzinfo=dt.timezone.utc), mood_score=8)
    db_session.add(m2)
    db_session.commit()

    res = compute_headache_summary(db_session, dt.date(2026, 10, 10), dt.date(2026, 10, 11))
    assert res["total_days"] == 2
    assert res["symptom_days"] == 1
    assert res["average_severity"] == 3.0


def test_hydration_unknown_when_zero_or_missing(db_session):
    # 0 ml hydration should be ignored as unknown
    db_session.add(models.GarminHydrationDaily(
        hydration_date=dt.date(2026, 10, 9), consumed_ml=0, goal_ml=2500
    ))
    db_session.commit()
    res = compute_headache_summary(db_session, dt.date(2026, 10, 10), dt.date(2026, 10, 11))
    # Hydration should not crash and should not treat 0 as 0%
    bio = next((b for b in res["biometrics"] if "Hydration" in b["metric"]), None)
    assert bio is None or bio["confidence"] == "too_early"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest tests/test_symptom_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.symptom_report'`

- [ ] **Step 3: Implement `backend/app/services/symptom_report.py`**

Implement `compute_headache_summary`:
1. Query `Mood` entries in the date range with selectinloaded `activities` and `activity_details`.
2. Determine `symptom_days` where any activity has `is_symptom(activity)` is True. Collect all numeric severities for `average_severity`.
3. Candidate activities:
   - For day-before triggers: activities logged on $d-1$ (or Before Sleep with `night_for_entry == d`). Filter by `effective_role == 'possible_cause'` and not hidden on `ACUPUNCTURE_PAGE`.
   - For same-day triggers: activities logged on $d$. Include `effective_role` in `('possible_cause', 'reaction')`.
4. Garmin Workouts the day before:
   - `Workout (day before)`
   - `Late workout (day before)` (after 18:00 or < 04:00)
   - `Long workout (> 45m)`
5. Garmin Biometrics:
   - `Sleep Score (night before)`: `GarminSleepDaily.sleep_score` for `sleep_date == d`.
   - `Overnight Stress (night before)`: `dailySleepDTO.avgSleepStress` or `GarminStressDaily`.
   - `Overnight HRV (night before)`: `GarminHRVDaily` payload last night average.
   - `Resting Heart Rate (day before)`: `GarminRestingHeartRateDaily` on $d-1$.
   - `Hydration (day before)`: `GarminHydrationDaily` on $d-1$, where `consumed_ml > 0` and `goal_ml > 0`, computed as `consumed_ml / goal_ml * 100`.
6. Run `compare()` for all candidates, apply `bh_adjust()` to p-values, detect twins (`logged_with`), sort by confidence and effect size.
7. Return payload dictionary with `triggers_day_before`, `triggers_same_day`, `biometrics`, `too_early`, `left_out`.

- [ ] **Step 4: Run test to verify it passes**

Run: `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest pytest tests/test_symptom_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/symptom_report.py backend/tests/test_symptom_report.py
git commit -m "feat(reports): implement symptom report computation service with shared comparison"
```

---

### Task 3: API Route Integration & Legacy Compatibility

**Files:**
- Modify: `backend/app/routes/reports.py:31-212`
- Test: `backend/tests/test_reports_api.py`

**Interfaces:**
- Produces: `GET /reports/headache-summary` returning new structured payload while preserving backwards-compatible fields (`triggers` and `biometrics` as aliases).
- Consumes: `symptom_report.compute_headache_summary`

- [ ] **Step 1: Write the failing API test**

```python
# backend/tests/test_reports_api.py
import datetime as dt
from fastapi.testclient import TestClient
from app.main import app

def test_headache_summary_endpoint(client):
    res = client.get("/reports/headache-summary")
    assert res.status_code == 200
    data = res.json()
    assert "triggers_day_before" in data
    assert "triggers_same_day" in data
    assert "biometrics" in data
    assert "left_out" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TEST_DATABASE_URL=... pytest tests/test_reports_api.py -v`
Expected: FAIL on `assert "triggers_day_before" in data`

- [ ] **Step 3: Update `backend/app/routes/reports.py`**

Refactor `get_headache_summary` to delegate to `compute_headache_summary(db, start_date, end_date)`.
Preserve `triggers` as an alias to `triggers_day_before` for legacy safety.

- [ ] **Step 4: Run test to verify it passes**

Run: `TEST_DATABASE_URL=... pytest tests/test_reports_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/reports.py backend/tests/test_reports_api.py
git commit -m "feat(reports): connect headache-summary route to symptom report service"
```

---

### Task 4: Frontend UI Redesign for Acupuncture & Symptom Report

**Files:**
- Modify: `frontend-web/src/routes/acupuncture-report/+page.svelte`

**Interfaces:**
- Consumes: `/reports/headache-summary`, `/activities/{id}/report-settings`, `/activities/{id}`
- Follows: `tokens.css` styling, Quiet Sanctuary design language, mobile responsive layout

- [ ] **Step 1: Update page state, types, and API loading**

Define types for `TriggerItem`, `BiometricItem`, `LeftOutItem`, `TooEarlyItem`.
Update `loadSummary` to populate `summary.triggers_day_before`, `summary.triggers_same_day`, `summary.biometrics`, `summary.too_early`, `summary.left_out`.

- [ ] **Step 2: Implement Lifestyle Impact styled list components**

1. Render "Possible triggers (the day and night before)" list with:
   - Activity name
   - Coloured effect tag (`+X% headache risk` in red `#b23b3b` or green `#2a7d4f`)
   - Exposure count (`· N days with, M without`)
   - 3-bar confidence meter & word label (`Strong`, `Some evidence`, `Weak`)
   - ⋯ menu button for activities or watch icon for Garmin metrics
   - Twin notes when items are always logged together
2. Render "Same day: could be a cause or a reaction" section with clear explanatory subtitle.
3. Render "Garmin measures (night and day before)" biometric section with difference and averages on symptom vs clean days.
4. Render "Too early to tell" section.
5. Render "Left out of this page" chips with removal `×` buttons that restore items.
6. Replace old "Exclude Activities" block.

- [ ] **Step 3: Implement ⋯ role menu logic for acupuncture report**

Add `chooseRole(activityId, role)` and `bringBack(item)`:
- Role choice options: "Just a habit I’m recording", "Describes how the night went", "Something I do because of a symptom", "Hide from this page only" (using page key `acupuncture_report`).

- [ ] **Step 4: Verify frontend typecheck and build**

Run: `cd frontend-web && npm run check && npm run build`
Expected: 0 errors, production build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend-web/src/routes/acupuncture-report/+page.svelte
git commit -m "feat(ui): update acupuncture and symptom report UI to shared row design and chips"
```

---

### Task 5: Verification, Version Bump & Release Preparation

**Files:**
- Modify: `frontend-web/package.json` (bump version to 4.21.0)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run full test suites locally**

1. Run backend pytest with Postgres:
   `TEST_DATABASE_URL=... pytest tests -v`
2. Run backend linter:
   `ruff check --select E4,E7,E9,F app`
3. Run preview script test harness:
   `bash scripts/tests/test_preview.sh`
4. Run frontend check and build:
   `cd frontend-web && npm run check && npm run build`

- [ ] **Step 2: Bump version and update CHANGELOG.md**

Update `frontend-web/package.json` to `"version": "4.21.0"`.
Add `## 4.21.0 (2026-11-05)` entry to `CHANGELOG.md` describing the new comparison method on the Acupuncture & Symptom Report page.

- [ ] **Step 3: Run differential security review**

Run differential security check on all branch modifications against `origin/main`.

- [ ] **Step 4: Commit and push**

```bash
git add frontend-web/package.json CHANGELOG.md
git commit -m "chore(release): bump version to 4.21.0 and document Stage 2 headache report"
git push -u origin feat/headache-report-comparison-26
```

- [ ] **Step 5: Create Pull Request**

Create GitHub PR linking Issue #26.
