# Acupuncture & Symptom Report Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Acupuncture & Symptom Report into a fast, visual “Clinic Brief” (headache & position breakdowns, day-by-day timeline, prior-period comparison) backed by an audited, statistically sound independent trigger analysis engine.

**Architecture:** Split the backend into two independent service functions and FastAPI endpoints (`GET /reports/headache-appointment-summary` for instant clinic stats/breakdowns/timeline, and `GET /reports/headache-triggers` for 90-day / All-time / This-period trigger & biometric analysis), keeping `GET /reports/headache-summary` backwards-compatible. Build the “Option A · Clinic Brief” UI in pure Svelte 5 / HTML / CSS / SVG with unit-tested date and verdict helpers in `frontend-web/src/lib/acupunctureReport.js`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0+, PostgreSQL, pytest, ruff, Svelte 5 / SvelteKit, TypeScript, raw CSS (`frontend-web/src/tokens.css`), Node `node:test`.

**Spec:** `docs/superpowers/specs/2026-11-19-acupuncture-report-redesign-design.md`

## Global Constraints

- No database schema changes or migrations.
- No new frontend or backend dependencies.
- All UI colours must use semantic tokens from `frontend-web/src/tokens.css` (deliberate data/status washes for headache amber and migraine coral follow `DESIGN.md` exceptions; zero drop shadows per Flat Sanctuary Rule; zero `0px` radii; single-column responsive collapse below `860px`).
- All dates use UK local timezone (`Europe/London`, `UK_TZ` in `backend/app/services/insight_dates.py`) on the backend and pure `YYYY-MM-DD` calendar math on the frontend.
- Existing `GET /reports/headache-summary` must remain backwards-compatible, including its `triggers` alias.
- Never commit or push to `main`; all work commits to a fresh branch created from `origin/main` (`acupuncture-report-redesign`).
- Public GitHub repo: never commit personal data, IPs, hostnames, or secrets.

## Review Focus

1. **Today’s session already logged before opening report at the appointment:** `sessions[0] == today` skips today and defaults to `sessions[1] + 1 .. today` (or last 30 days if none), and today’s session is omitted from the `Since <date>` dropdown (pinned in Task 4).
2. **Same-day multi-entry & deprecated duplicate activity folding:** Logging `Headache` twice and `Migraine` once on the same day counts `1` symptom day, `Headache: 1`, `Migraine: 1`, colours the day cell `migraine`, and folds deprecated same-named copies into the current activity (pinned in Task 1).
3. **Prior period with zero logged moods vs. logged moods with zero headaches:** An unlogged prior window returns `previous_period: null` (omitting the delta pill), while a logged prior window with zero headaches returns `frequency: 0` (pinned in Task 1).
4. **UK BST late-evening / post-midnight timestamps:** Moods at `23:30 UTC` during BST (`00:30 BST` next day) map to the UK calendar date for both acupuncture sessions and symptom counts; `Before Sleep` items logged at `00:30` local time count only in `triggers_day_before` and never in `triggers_same_day` (pinned in Tasks 1, 2, 3).
5. **Empty database or zero symptom days across `This period`, `90 days`, and `All time`:** No division-by-zero, `None` crashes, or HTTP 500s; summary returns an all-clear timeline and triggers return `verdict_kind: "insufficient_data"` (pinned in Tasks 1, 2, 3).

---

### File Structure

- Modify: `backend/app/services/symptom_report.py` — decompose into `get_acupuncture_session_dates`, `compute_appointment_summary`, `compute_headache_triggers`, and backwards-compatible `compute_headache_summary`.
- Modify: `backend/app/routes/reports.py` — fix UK timezone on `/acupuncture-sessions`, add `/headache-appointment-summary` and `/headache-triggers`, validate `start_date <= end_date` (HTTP 400).
- Modify: `backend/tests/test_symptom_report.py` — Postgres unit/integration tests for appointment summary, breakdowns, timeline, prior-period rules, and every audited trigger/biometric fix.
- Modify: `backend/tests/test_reports_api.py` — API contract, validation (HTTP 400), UK session timezone, and backwards-compatibility tests.
- Create: `frontend-web/src/lib/acupunctureReport.js` + `frontend-web/src/lib/acupunctureReport.d.ts` + `frontend-web/src/lib/acupunctureReport.test.js` — pure calendar-date, session-default, verdict-copy, and bar-scale helpers tested via `node --test`.
- Modify: `frontend-web/src/routes/acupuncture-report/+page.svelte` — “Option A · Clinic Brief” redesign with independent parallel fetching, day-by-day strip, breakdown bars, segmented trigger window toggle, verdict banner, visual risk bars, and collapsible secondary drawers.

---

### Task 1: Appointment Summary Service & UK Session Dates

**Files:**
- Modify: `backend/app/services/symptom_report.py`
- Test: `backend/tests/test_symptom_report.py`

**Interfaces:**
- Consumes: `models.Mood`, `models.Activity`, `models.Category`, `models.MoodActivityDetail`, `UK_TZ` from `backend/app/services/insight_dates.py`, `is_symptom` from `backend/app/services/item_roles.py`.
- Produces:
  - `get_acupuncture_session_dates(db: Session) -> list[dt.date]` (descending unique `UK_TZ` dates of moods tagged with `%acupuncture%` activity).
  - `compute_appointment_summary(db: Session, start_date: dt.date | None = None, end_date: dt.date | None = None) -> dict` returning:
    ```python
    {
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "total_days": int,
        "symptom_days": int,
        "clean_days": int,
        "frequency": int,  # rounded percentage 0..100
        "average_severity": float | None,
        "previous_period": {
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "total_days": int,
            "symptom_days": int,
            "frequency": int,
            "comparison_type": "previous_session_gap" | "equal_length_prior",
        } | None,
        "symptom_breakdown": [{"activity_id": int, "activity": str, "days": int, "is_migraine": bool}],
        "position_breakdown": [{"position": str, "days": int}],
        "daily_timeline": [
            {
                "date": "YYYY-MM-DD",
                "status": "clear" | "headache" | "migraine",
                "symptoms": list[str],
                "positions": list[str],
                "has_acupuncture": bool,
            }
        ],
    }
    ```

- [ ] **Step 1: Create branch `acupuncture-report-redesign` from `origin/main` and verify Postgres test runner works**

Run: `git checkout -b acupuncture-report-redesign origin/main`
Start throwaway Postgres container (if not already running) and verify `cd backend && TEST_DATABASE_URL=<url> pytest tests/test_symptom_report.py -q` passes before editing.

- [ ] **Step 2: Write failing tests in `backend/tests/test_symptom_report.py`**

Add tests pinning every appointment-summary requirement and Review Focus items 2, 3, 4, 5:
- `test_appointment_summary_breakdowns_hide_zeros_and_fold_deprecated`: creates `Headache Issues` activities (`Headache` active + deprecated duplicate `Headache`, `Migraine`, `Sinus Pressure` unlogged), logs `Headache` twice and `Migraine` once on Day 1 (with positions `["Left", "Forehead"]`), deprecated `Headache` on Day 2 (with plain-string position `"Left"`), clean mood on Day 3. Asserts:
  - `symptom_days == 2`, `total_days == 3`, `frequency == 67`
  - `symptom_breakdown == [{"activity_id": headache_active.id, "activity": "Headache", "days": 2, "is_migraine": False}, {"activity_id": migraine.id, "activity": "Migraine", "days": 1, "is_migraine": True}]` (`Sinus Pressure` omitted)
  - `position_breakdown == [{"position": "Left", "days": 2}, {"position": "Forehead", "days": 1}]`
  - Day 1 timeline entry has `status == "migraine"`, `symptoms == ["Headache", "Migraine"]`, `positions == ["Forehead", "Left"]` (or sorted); Day 2 has `status == "headache"`; Day 3 has `status == "clear"`.
- `test_appointment_summary_severity_ignores_entries_outside_window`: logs severity `5` on `start_date - 1 day` and severity `2` inside window; asserts `average_severity == 2.0`.
- `test_appointment_summary_prior_period_session_gap_vs_equal_window_and_unlogged`:
  - Sessions on Oct 1 and Oct 10, viewing Oct 11..Oct 20 (`start_date - 1 == Oct 10`, no session inside `[Oct 11, Oct 20)`): compares against `Oct 2..Oct 10` (`comparison_type == "previous_session_gap"`).
  - Unlogged prior window returns `previous_period is None`.
  - Logged prior window with 0 headaches returns `previous_period["frequency"] == 0`.
  - Custom window (or multi-session span containing Oct 10 inside `[start, end)`) compares against equal-length prior window (`comparison_type == "equal_length_prior"`).
- `test_acupuncture_sessions_use_uk_bst_date_and_empty_db_summary`:
  - Mood with `Acupuncture` logged at `2026-07-10 23:30 UTC` (`2026-07-11 00:30 BST`) resolves session date to `dt.date(2026, 7, 11)`.
  - Empty DB returns `symptom_days == 0`, `frequency == 0`, `previous_period is None`, `symptom_breakdown == []`, `position_breakdown == []`, and `len(daily_timeline) == total_days` all `"clear"`.

- [ ] **Step 3: Run the new tests to confirm they fail**

Run: `cd backend && TEST_DATABASE_URL=<url> pytest tests/test_symptom_report.py -v`
Expected: FAIL (`ImportError: cannot import name 'compute_appointment_summary'`).

- [ ] **Step 4: Implement `get_acupuncture_session_dates` and `compute_appointment_summary` in `backend/app/services/symptom_report.py`**

Key implementation details pinned by spec:
- Raise `ValueError("start_date must be on or before end_date")` if `start_date > end_date`.
- Parse `MoodActivityDetail.position` using a helper matching `_normalize_positions` in `backend/app/routes/mood.py` (JSON array or plain string fallback, stripped & deduplicated).
- Fold deprecated copies via `_group_old_and_current_copies` before counting distinct symptom days per primary activity.
- Mark `is_migraine = "migraine" in name.lower()`. Timeline cell `status` is `"migraine"` if any symptom on that day has `is_migraine`, else `"headache"` if any symptom on that day, else `"clear"`.
- Mark `has_acupuncture = day in session_date_set` on each timeline day.
- Prior-period resolution:
  - Let `anchor = start_date - dt.timedelta(days=1)`.
  - If `anchor in session_date_set` and no session falls in `[start_date, end_date)` and there is an earlier session `prev_session < anchor`: prior window is `[prev_session + 1 day, anchor]`, `comparison_type = "previous_session_gap"`.
  - Else: prior window is `[start_date - total_days, start_date - 1 day]`, `comparison_type = "equal_length_prior"`.
  - Query moods in prior window (`UK_TZ` bounds). If zero moods exist in the prior window, set `previous_period = None`; otherwise compute `symptom_days`, `total_days`, and `frequency`.
- Count `symptom_severities` ONLY when `in_window(mood_date)`.

- [ ] **Step 5: Run tests to verify Task 1 passes**

Run: `cd backend && TEST_DATABASE_URL=<url> pytest tests/test_symptom_report.py -v`
Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add docs/superpowers/specs/2026-11-19-acupuncture-report-redesign-design.md docs/superpowers/plans/2026-11-19-acupuncture-report-redesign.md backend/app/services/symptom_report.py backend/tests/test_symptom_report.py
git commit -m "feat(reports): add appointment summary service with breakdowns, timeline, and UK timezone"
```

---

### Task 2: Audited Trigger & Biometric Analysis Engine (`compute_headache_triggers`)

**Files:**
- Modify: `backend/app/services/symptom_report.py`
- Test: `backend/tests/test_symptom_report.py`

**Interfaces:**
- Consumes: `compare`, `bh_adjust`, `level_for`, `is_negligible`, `CONFIDENCE_ORDER`, `MIN_NIGHTS` from `backend/app/services/comparison.py`; `UK_TZ`, `is_late_workout`, `night_for_entry`, `night_for_workout` from `backend/app/services/insight_dates.py`; `ACUPUNCTURE_PAGE`, `effective_role`, `is_before_sleep`, `is_hidden_on`, `is_symptom`, `role_was_set_by_owner` from `backend/app/services/item_roles.py`.
- Produces:
  - `TRIGGER_WINDOWS = ("period", "90d", "all")`
  - `compute_headache_triggers(db: Session, window: str = "90d", start_date: dt.date | None = None, end_date: dt.date | None = None) -> dict` returning:
    ```python
    {
        "window": "period" | "90d" | "all",
        "start_date": "YYYY-MM-DD" | None,
        "end_date": "YYYY-MM-DD" | None,
        "logged_days": int,
        "symptom_days": int,
        "clean_days": int,
        "tested_count": int,
        "clue_count": int,
        "verdict_kind": "clues_found" | "looks_random" | "insufficient_data",
        "triggers_day_before": list[dict],   # strong/some, non-negligible
        "triggers_same_day": list[dict],     # strong/some, non-negligible, non-Before-Sleep, non-reaction
        "biometrics": list[dict],            # strong/some, non-negligible, BH-adjusted
        "no_clear_link": list[dict],         # deduplicated weak/negligible activities, workouts & biometrics
        "too_early": list[dict],             # deduplicated < MIN_NIGHTS activities, workouts & biometrics
        "left_out": list[dict],              # habit, describes_night, reaction, hidden
        "min_nights": int,
    }
    ```
    Each `no_clear_link` entry includes `"kind": "activity" | "garmin_workout" | "biometric"` (and `"timing": "day_before" | "same_day" | "biometric"`), plus the standard fields (`activity_id`, `activity`, `effect`, `with_nights`, `without_nights`, `confidence`, `better`, `source`, `logged_with` for triggers; `metric`, `symptom_avg`, `clean_avg`, `effect`, `unit`, `confidence`, `better` for biometrics).
  - `compute_headache_summary(db: Session, start_date: dt.date | None = None, end_date: dt.date | None = None) -> dict` — updated backwards-compatible wrapper combining `compute_appointment_summary` and `compute_headache_triggers(db, window="period", ...)` so existing callers/tests get all original keys plus the new fields.

- [ ] **Step 1: Write failing tests in `backend/tests/test_symptom_report.py`**

Add tests pinning every audited logic fix and Review Focus items 4 & 5:
- `test_triggers_exclude_unlogged_days_from_baseline`: over 30 calendar days, user only logs on 12 days (6 with `Wine` on `d-1` + headache on `d`, 6 clean days without `Wine`), and leaves 18 days completely blank. Asserts `without_nights == 6` (not `24`) and `logged_days == 12`.
- `test_before_sleep_never_appears_in_same_day_even_after_midnight`: logs `Before Sleep` item `Magnesium` at `00:30` local time on headache days across 12 days. Asserts `Magnesium` is evaluated ONLY in `day_before` and NEVER appears in `triggers_same_day` or as a `same_day` item in `no_clear_link`.
- `test_reaction_excluded_from_triggers_and_included_in_left_out`: marks `Ibuprofen` as `report_role="reaction"`, logs on all 6 headache days out of 12. Asserts `Ibuprofen` is NOT in `triggers_day_before`, NOT in `triggers_same_day`, NOT in `no_clear_link`, and IS in `left_out` with `reason == "reaction"`.
- `test_weak_and_zero_effects_go_to_no_clear_link_and_verdict_looks_random`: logs an activity equally on 5 headache days and 5 clean days (`0%` difference). Asserts `triggers_day_before == []`, `clue_count == 0`, `tested_count >= 1`, `verdict_kind == "looks_random"`, and the item appears once (deduplicated) in `no_clear_link` (NOT duplicated across `day_before` and `same_day`).
- `test_clue_suppressed_from_no_clear_link_and_too_early`: activity is a strong clue in `day_before` and weak in `same_day`; asserts it appears in `triggers_day_before` and does NOT appear in `no_clear_link` or `too_early`.
- `test_too_early_deduplicated_across_day_before_and_same_day`: daytime activity logged 3 times appears only ONCE in `too_early`.
- `test_biometrics_bh_adjusted_negligible_filtered_hrv_paths_and_stress_fallback`:
  - Uses `hrvSummary.lastNight` (one of the 8 paths) and verifies HRV is read.
  - Uses `GarminStressDaily` fallback (when `avgSleepStress` absent) on `d - 1` and verifies metric label is `"Daytime Stress (day before)"` (NOT `"Overnight Stress (night before)"`).
  - Zero-difference biometric is routed to `no_clear_link` (with `kind == "biometric"`), not `biometrics` clues.
- `test_garmin_midnight_workout_uses_night_for_workout`: workout at `00:30 UTC` on `d` affects day `d` (not `d + 1`).
- `test_triggers_window_90d_all_and_empty_db`: verifies `window="90d"`, `window="all"`, and empty DB (`verdict_kind == "insufficient_data"`, `logged_days == 0`).
- Update existing `test_day_before_and_same_day_separation` in `backend/tests/test_symptom_report.py` so it reflects the spec decision that `reaction` (`Ibuprofen`) is excluded from `triggers_same_day` and placed in `left_out`, while a same-day `possible_cause` (e.g. `Skipped Lunch`) appears in `triggers_same_day`.

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd backend && TEST_DATABASE_URL=<url> pytest tests/test_symptom_report.py -v`
Expected: FAIL (`ImportError: cannot import name 'compute_headache_triggers'`).

- [ ] **Step 3: Implement `compute_headache_triggers` and update `compute_headache_summary` in `backend/app/services/symptom_report.py`**

Key algorithmic rules pinned by spec:
- Resolve window dates:
  - `window == "period"`: use `(start_date, end_date)` (defaulting to last 30 days if omitted); raise `ValueError` if `start_date > end_date`.
  - `window == "90d"`: `end = today (UK_TZ)`, `start = end - 89 days`.
  - `window == "all"`: find earliest `Mood.timestamp` (converted to `UK_TZ` date); if none, return empty `insufficient_data` payload; else `start = earliest`, `end = today`.
  - Invalid `window` raises `ValueError`.
- Track `active_logged_days: set[dt.date]` (all `UK_TZ` dates with `>= 1` mood entry inside `[start, end]` — and also track `exposure_logged_days` across `[start - 2 days, end]` so day-before `without_set` checks whether `d - 1` had any logging!).
  - Specifically, for a day `d in active_logged_days`:
    - `d` is eligible for **day-before** comparison (`without_set`) if `d - 1 day` is in `exposure_logged_days` (the user logged something on the day before) AND `d not in with_set`.
    - `d` is eligible for **same-day** comparison (`without_set`) if `d in active_logged_days` AND `d not in with_set`.
  - `clean_days = active_logged_days - symptom_days`.
- Roles:
  - `explicit_left_out` query includes `report_role.in_(["habit", "describes_night", "reaction"]) | hidden_pages.isnot(None)`.
  - `role == "reaction"`: add to `left_out_dict` with `reason = "reaction"` (if set by owner) and skip both `candidates_day_before` and `candidates_same_day`.
  - `Before Sleep` category (`is_before_sleep(category_name)`): ONLY add to `day_before_item_days` (via `night_for_entry(mood.timestamp, True)`), NEVER to `same_day_item_days`.
- Garmin workouts:
  - `day_affected = night_for_workout(start_time)` if `start_time is not None` else `act_date + dt.timedelta(days=1)`.
  - `eligible_workout_days = {d for d in active_logged_days if d >= earliest_tracked_day}` (using `night_for_workout` on earliest activity).
- Evaluation & filtering:
  - Binary triggers: run `compare(with_vals, without_vals)` + `bh_adjust` across tested items in each bucket (`day_before` and `same_day`). An item is a **clue** iff `confidence in ("strong", "some")` AND `abs(effect_pct) >= 5` AND `not is_negligible(result.effect, with_vals + without_vals)`. Otherwise it is a **no_clear_link** candidate.
  - Biometrics: collect all 5 biometrics (with full 8 HRV paths and `GarminStressDaily` fallback shifted `+1 day` and labelled `"Daytime Stress (day before)"`), run `compare(symp_vals, clean_vals)` on each, add `< MIN_NIGHTS` metrics to `too_early_biometrics`, run `bh_adjust` across all tested biometrics, then classify as **clue** iff `confidence in ("strong", "some")` AND `not is_negligible(res.effect, symp_vals + clean_vals)` AND `round(diff, 1) != 0.0`, else **no_clear_link** (`kind = "biometric"`).
- Cross-bucket deduplication:
  - `clue_activity_ids = {item["activity_id"] for item in triggers_day_before + triggers_same_day if item["activity_id"] is not None}`.
  - `evaluated_activity_ids` = all activity IDs that passed `MIN_NIGHTS` in either `day_before` or `same_day`.
  - For `no_clear_link`: drop any activity in `clue_activity_ids`; if an activity is in both `day_before` and `same_day` weak lists, keep only the `day_before` entry; append weak Garmin workouts and weak biometrics.
  - For `too_early`: drop any activity in `evaluated_activity_ids`; deduplicate by `(activity_id, activity)` keeping max `with_nights`; include `too_early` biometrics.
- Verdict:
  - `clue_count = len(triggers_day_before) + len(triggers_same_day) + len(biometrics)`
  - `tested_count = clue_count + len(no_clear_link)`
  - `verdict_kind`:
    - `"clues_found"` if `clue_count > 0`
    - `"looks_random"` if `clue_count == 0` and `tested_count > 0` and `len(symptom_days) >= MIN_NIGHTS` and `len(clean_days) >= MIN_NIGHTS`
    - `"insufficient_data"` otherwise.

- [ ] **Step 4: Run full backend test suite**

Run: `cd backend && TEST_DATABASE_URL=<url> pytest tests -q`
Expected: All tests PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/services/symptom_report.py backend/tests/test_symptom_report.py
git commit -m "feat(reports): audit and fix headache trigger and biometric logic"
```

---

### Task 3: Reports API Endpoints & Input Validation

**Files:**
- Modify: `backend/app/routes/reports.py`
- Test: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: `get_acupuncture_session_dates`, `compute_appointment_summary`, `compute_headache_triggers`, `compute_headache_summary`, `TRIGGER_WINDOWS` from `backend/app/services/symptom_report.py`.
- Produces HTTP endpoints:
  - `GET /reports/acupuncture-sessions` -> `{"sessions": ["YYYY-MM-DD", ...]}` (UK local dates, descending)
  - `GET /reports/headache-appointment-summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` -> appointment summary JSON (HTTP 400 if `start_date > end_date`)
  - `GET /reports/headache-triggers?window=90d|all|period&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` -> triggers JSON (HTTP 400 if invalid `window` or `start_date > end_date`)
  - `GET /reports/headache-summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` -> backwards-compatible combined JSON (HTTP 400 if `start_date > end_date`, preserves `triggers` alias)

- [ ] **Step 1: Write failing API tests in `backend/tests/test_reports_api.py`**

Add tests:
- `test_appointment_summary_endpoint_and_bad_range`: verifies 200 payload keys (`symptom_breakdown`, `position_breakdown`, `daily_timeline`, `previous_period`, `total_days`, `symptom_days`, `frequency`) and HTTP 400 when `start_date > end_date`.
- `test_headache_triggers_endpoint_windows_and_validation`: verifies `window=90d`, `window=all`, `window=period&start_date=...&end_date=...` return 200 with `verdict_kind`, `no_clear_link`, `triggers_day_before`, `biometrics`, `too_early`, `left_out`; verifies HTTP 400 on invalid `window=foo` and on `window=period` with `start_date > end_date`.
- `test_acupuncture_sessions_endpoint_uses_uk_timezone`: logs an Acupuncture mood at `2026-07-10T23:30:00Z` and asserts `/reports/acupuncture-sessions` returns `["2026-07-11"]`.

- [ ] **Step 2: Run API tests to verify they fail**

Run: `cd backend && TEST_DATABASE_URL=<url> pytest tests/test_reports_api.py -v`
Expected: FAIL (404 on new routes / UTC date on acupuncture-sessions).

- [ ] **Step 3: Implement routes in `backend/app/routes/reports.py`**

Wire all four routes to `symptom_report.py`, raising `HTTPException(status_code=400, detail=str(exc))` on `ValueError` (invalid window or `start_date > end_date`).

- [ ] **Step 4: Run full backend tests and ruff lint**

Run: `cd backend && TEST_DATABASE_URL=<url> pytest tests -q`
Run: `ruff check --select E4,E7,E9,F backend/app`
Expected: Both PASS with 0 errors.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/app/routes/reports.py backend/tests/test_reports_api.py
git commit -m "feat(reports): add split appointment summary and headache trigger endpoints"
```

---

### Task 4: Frontend Pure Helpers & Unit Tests

**Files:**
- Create: `frontend-web/src/lib/acupunctureReport.js`
- Create: `frontend-web/src/lib/acupunctureReport.d.ts`
- Create: `frontend-web/src/lib/acupunctureReport.test.js`

**Interfaces:**
- Produces:
  - `addDaysIso(isoDate: string, days: number): string` — pure UTC calendar math on `YYYY-MM-DD` (never shifts across browser timezones or DST).
  - `pastSessionsBefore(sessions: string[], todayIso: string): string[]` — filters sessions strictly `< todayIso`.
  - `pickDefaultSessionWindow(sessions: string[], todayIso: string): { startDate: string; endDate: string; selectedSession: string }` — picks `pastSessions[0] + 1 day .. todayIso`, or `todayIso - 29 days .. todayIso` if no prior session exists (Review Focus #1).
  - `barWidthPercent(value: number, maxValue: number): number` — safe `0..100` percentage (min visible floor `6%` when `value > 0`, `0` when `<= 0`).
  - `describeVerdict(data: { verdict_kind: string; clue_count: number; logged_days: number; symptom_days: number; window: string; min_nights: number }): { headline: string; detail: string }` — plain-English Clinic Brief verdict text.
  - `formatDeltaPill(currentFreq: number, previous: { frequency: number; comparison_type: string } | null): { text: string; tone: 'better' | 'worse' | 'neutral' } | null` — e.g. `↓ from 52%` (`better`), `↑ from 30%` (`worse`), `Same as prior` (`neutral`), or `null`.

- [ ] **Step 1: Write failing tests in `frontend-web/src/lib/acupunctureReport.test.js`**

Write `node:test` assertions covering:
- `addDaysIso` across month boundaries, leap years, and UK DST transition dates (`2026-03-28 + 1 == 2026-03-29`, `2026-10-25 + 1 == 2026-10-26`).
- `pickDefaultSessionWindow` when `sessions[0] === todayIso` (skips today, uses `sessions[1] + 1`), when only today's session exists (falls back to 30-day window), and when sessions are empty.
- `pastSessionsBefore` excludes today and future dates.
- `formatDeltaPill` for lower frequency (`better`), higher frequency (`worse`), equal frequency (`neutral`), and `null` prior period (`null`).
- `describeVerdict` for `clues_found` (singular `1 clue` & plural `2 clues`), `looks_random`, and `insufficient_data` (suggesting 90 days / All time when on `period`).

- [ ] **Step 2: Run frontend helper tests to verify they fail**

Run: `cd frontend-web && node --test src/lib/acupunctureReport.test.js`
Expected: FAIL (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 3: Implement `frontend-web/src/lib/acupunctureReport.js` and `frontend-web/src/lib/acupunctureReport.d.ts`**

Implement the exact exported functions and TypeScript declarations cleanly with JSDoc/types matching `frontend-web/src/lib/errors.js` + `errors.d.ts`.

- [ ] **Step 4: Run all frontend helper tests**

Run: `cd frontend-web && node --test src/lib/*.test.js`
Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add frontend-web/src/lib/acupunctureReport.js frontend-web/src/lib/acupunctureReport.d.ts frontend-web/src/lib/acupunctureReport.test.js
git commit -m "feat(web): add unit-tested date, session, and verdict helpers for acupuncture report"
```

---

### Task 5: Acupuncture Report Page Redesign (“Option A · Clinic Brief”) & Full Verification

**Files:**
- Modify: `frontend-web/src/routes/acupuncture-report/+page.svelte`

**Interfaces:**
- Consumes:
  - `GET /reports/acupuncture-sessions`
  - `GET /reports/headache-appointment-summary`
  - `GET /reports/headache-triggers`
  - `GET /activities/{id}`, `PUT /activities/{id}/report-settings`
  - Helpers from `$lib/acupunctureReport.js` and `describeError` from `$lib/errors.js`.

- [ ] **Step 1: Read Impeccable craft floor before UI editing**

Read `/home/andyl/.gemini/config/skills/impeccable/reference/craft-floor.md` (required by Impeccable skill before any UI edit) and inspect `frontend-web/src/routes/acupuncture-report/+page.svelte` against `DESIGN.md` and `tokens.css`.

- [ ] **Step 2: Redesign `frontend-web/src/routes/acupuncture-report/+page.svelte`**

Implement “Option A · Clinic Brief” with all spec requirements:
1. **Independent state & parallel loading:**
   - Separate `summaryLoading`/`summaryError`/`summary` and `triggersLoading`/`triggersError`/`triggers` states so the top Clinic Brief renders immediately while trigger stats finish, and changing dates/sessions does not reload `90d`/`all` triggers (only reloads triggers when `triggerWindow === 'period'`).
   - Use UK local today (`en-CA` formatter with `timeZone: 'Europe/London'`) + `pickDefaultSessionWindow` so initial load never breaks if today’s session is already logged.
   - Validate `startDate <= endDate` inline before fetching (showing a clear friendly error message if reversed).
2. **Compact Timeframe Bar:**
   - “Quick Select Session” dropdown populated by `pastSessionsBefore(sessions, todayIso)` (`Since <date>`) bound cleanly to `selectedSession`, alongside Start Date and End Date inputs (min 44px touch targets on mobile).
3. **Appointment Summary Card (Clinic Brief):**
   - Stat strip (`Symptom Days`, `Total Days`, `Frequency` with optional delta pill from `formatDeltaPill`, plus `Avg Severity` only when non-null).
   - **Day-by-Day Timeline Strip (“When symptoms happened”):**
     - Renders each day in `summary.daily_timeline` as a button cell (`clear`, `headache`, `migraine`, plus small top-right acupuncture dot when `has_acupuncture`).
     - Uses numbered day cells for `<= 60` days and compact heat-squares (no cramped numbers) for `> 60` days so long periods stay clean on mobile with zero horizontal overflow.
     - Clicking/tapping any cell opens a quiet inline detail bar right below the strip showing formatted date, logged symptom names, positions, and acupuncture badge (keyboard accessible + native `title` for hover).
     - Compact legend (`Clear`, `Headache`, `Migraine`, plus `Acupuncture` only when any day in range has `has_acupuncture`).
   - **Breakdown Columns (2-column grid collapsing to 1 column below `860px`):**
     - **Headache Types:** horizontal proportional bars (`Headache`, `Migraine`, etc.) with distinct day count; only renders logged items (`> 0`). If `symptom_breakdown` is empty, displays a calm “No headaches logged in this period” note.
     - **Positions Logged:** horizontal proportional bars for logged positions; completely omitted when `position_breakdown.length === 0` so Headache Types spans full width.
4. **Possible Triggers Card (bottom):**
   - Header with segmented radio/button toggle (`This period` | `90 days` | `All time`), `90 days` selected by default.
   - Plain-English **Verdict Banner** rendered from `describeVerdict(...)` (with a quick one-tap button to switch to `90 days` when `verdict_kind === 'insufficient_data'` and `triggerWindow === 'period'`).
   - Clue lists (`Day & night before`, `Contributing biometrics (Garmin)`, `Same day: could be a cause or a reaction`) — each row shows a small visual directional effect bar, signed effect text, sample counts/averages, twin note if present, 3-bar confidence meter, and `···` role/hide menu (for activities) or watch badge (for Garmin items).
   - **Collapsible Secondary Drawers (`<details>`):**
     - `Checked, no clear link (N)` — renders weak/negligible activities (with `···` role/hide menu!), Garmin workouts, and Garmin biometrics (with watch badge + diff/averages).
     - `Too early to tell (N)` — deduplicated list of activities, workouts, and biometrics below `min_nights`.
     - `Left out of this page (N)` — chip list for `habit`, `describes_night`, `reaction`, `hidden`, with one-click restore (`×`).
   - Saving any role/hide/restore action reloads `loadTriggers()` cleanly (and never flashes the top Appointment Summary!).
5. **Design & Accessibility compliance:**
   - All blue/neutral/status colours from `tokens.css` (deliberate warm amber & muted coral washes for headache/migraine cells & bars).
   - Zero `box-shadow`, all corners `>= 6px` (`10px`/`12px`/`16px`/`999px` per `DESIGN.md`), proper heading hierarchy (keep `<h2>` on branch from `origin/main` so it doesn't conflict with `one-h1`, or match existing page heading level), `type="button"` on every non-submit button, focus-visible outlines, `prefers-reduced-motion` respected.

- [ ] **Step 3: Run frontend typecheck, build, helper tests, and Impeccable mechanical detector**

Run:
- `cd frontend-web && npx svelte-kit sync && npm run check`
- `cd frontend-web && npm run build`
- `cd frontend-web && node --test src/lib/*.test.js`
- `/home/andyl/.gemini/config/skills/impeccable/scripts/impeccable detect --json frontend-web/src/routes/acupuncture-report/+page.svelte`

Fix any findings in one clean batch and re-verify.

- [ ] **Step 4: Run full CI verification, security & safe-change checks, and preview**

Run everything CI runs plus safe-change checks:
- Backend tests on real Postgres: `cd backend && TEST_DATABASE_URL=<url> pytest tests -q`
- Backend lint: `ruff check --select E4,E7,E9,F backend/app`
- Script tests: `bash scripts/tests/test_preview.sh && bash scripts/tests/test_restore_dump.sh && bash scripts/tests/test_sync_backups_to_google.sh && bash scripts/tests/test_host_config_and_cron.sh && bash scripts/tests/test_db_backup_schedule.sh`
- Frontend check, build, and tests
- Secrets scan (`gitleaks` on commits and working tree, with `--redact`)
- Run `pwa-failure-points` quick check and `differential-review` on the whole branch
- Start preview (`scripts/preview.sh up`), inspect both desktop and mobile views (if safe / no health data viewed), and prepare the plain-English hand-over block with try-out list and live-check list.

- [ ] **Step 5: Commit Task 5 and push branch**

```bash
git add frontend-web/src/routes/acupuncture-report/+page.svelte
git commit -m "feat(web): redesign acupuncture report as Clinic Brief with visual breakdowns and trigger verdict"
```

---

## Rollout Notes

- No database backup or migration required (zero schema changes).
- No `.env` changes required on the NUC host.
- One plain-English `CHANGELOG.md` entry + version bump added on the branch just before merge go-ahead.
