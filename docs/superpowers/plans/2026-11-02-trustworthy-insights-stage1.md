# Trustworthy Insights, Stage 1: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Lifestyle Impact page and the dashboard advice give believable results. Match each item to the right night, compare nights with and without it, show how sure the app is, and let the owner set an item's role from the row.

**Architecture:** Three small backend services hold the logic: item roles, night matching and the with/without comparison. They sit under `backend/app/services/` so that stage 2 (the headache report) can reuse them. `routes/lifestyle_impact.py` is rewritten to use them. A new activity endpoint saves roles. The Svelte page is rebuilt as one ranked list with a ⋯ menu on each row.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL 15 and Python 3.11 stdlib only (`statistics`, `random`, `zoneinfo`; no new dependencies), plus SvelteKit with Svelte 5 and raw CSS tokens.

**Spec:** `docs/superpowers/specs/2026-11-02-trustworthy-insights-design.md`. This plan covers stage 1 only.

**Planner rules:** `agents/planner_agent.md`. The steps below include its required backup step and rollout notes.

## Global Constraints

- Work on branch `feature/trustworthy-insights`. Never commit to or push `main`. Commit by explicit path. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The repo is public. Tests and docs use made-up data only. No real figures, hostnames or IPs.
- No new dependencies. The stdlib only for statistics.
- The schema changes are additive only: two nullable columns on `activities`, added both in `models.py` and in `_ensure_legacy_schema_compatibility()` in `backend/app/database.py`.
- Local time is `ZoneInfo("Europe/London")`. tzdata is already installed in `backend/Dockerfile`.
- Minimum nights: **5 with and 5 without**. Below that, an item is "too early".
- The period options are **28, 84 and 182 days** (4w default, 12w, 26w). 7 days is removed.
- The midday rule applies to the **Before Sleep** category only: a Before Sleep entry logged at local time before 12:00 counts as the previous evening.
- A late workout is one with a local start time of **18:00 or later**.
- UI copy is British English, in plain words. Colours use tokens in `frontend-web/src/tokens.css`. Follow DESIGN.md ("Quiet Sanctuary").
- Backend tests use a real Postgres:
  `podman run -d --rm --name sleeptest -e POSTGRES_PASSWORD=test -e POSTGRES_DB=sleeptest -p 55432:5432 postgres:15`
  then `cd backend && TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/sleeptest venv/bin/pytest tests -q`

## Review Focus

1. **Clocks changing (BST to GMT).** An entry at 23:30 UTC in summer is 00:30 local time. A Before Sleep entry at that time still belongs to the evening that has just passed. Test in Task 3.
2. **Items with no category, or a renamed category.** They default to "possible cause" and must not crash. Test in Task 2.
3. **Garmin data with missing fields** (no `lastNightAvg`, no `avgSleepStress`, `None` scores). That night is skipped for that measure; the request doesn't fail with a 500 error. Test in Task 5.
4. **A period with no Garmin data at all.** The page returns empty lists and `avg_value: null`. Test in Task 5.
5. **The same item logged twice for one night** (two mood entries). It counts as one "with" night. Test in Task 5.

---

### Task 0: Confirm Garmin's sleep date and save the design

This decides the night shift, so it comes first. It's read-only.

**Files:**
- Commit: `docs/superpowers/specs/2026-11-02-trustworthy-insights-design.md`, `docs/superpowers/plans/2026-11-02-trustworthy-insights-stage1.md`

- [ ] **Step 1:** Run `scripts/preview.sh up`. Then, in the preview database, run:
  `SELECT sleep_date, sleep_start, sleep_end FROM garmin_sleep_daily ORDER BY sleep_date DESC LIMIT 5;`
  Expected: `sleep_end` (UK time) falls on `sleep_date`, and `sleep_start` is the evening before. **If not, stop and report to the owner.** The +1 night shift in Task 3 would be wrong.
- [ ] **Step 2:** In the same database, check what's in the saved Garmin data:
  `SELECT payload->'hrvSummary'->'lastNightAvg', payload->'dailySleepDTO'->'avgSleepStress' FROM garmin_hrv_daily h JOIN garmin_sleep_daily s ON s.sleep_date=h.hrv_date ORDER BY h.hrv_date DESC LIMIT 5;`
  Record which keys are present. If either is missing, use the fallback key names from Task 5 Step 3, and tell the owner.
- [ ] **Step 3:** `scripts/preview.sh down`
- [ ] **Step 4: Commit**
  ```bash
  git add docs/superpowers/specs/2026-11-02-trustworthy-insights-design.md docs/superpowers/plans/2026-11-02-trustworthy-insights-stage1.md
  git commit -m "docs: design and stage 1 plan for trustworthy lifestyle insights"
  ```

---

### Task 1: Store item roles (schema)

**Owner approval required before this task.** It changes the data format. Before it goes live, take a production backup (see Rollout).

**Files:**
- Modify: `backend/app/models.py` (class `Activity`)
- Modify: `backend/app/database.py` (`_ensure_legacy_schema_compatibility`, next to the `ignore_in_reports` block, about line 88)
- Modify: `backend/app/schemas.py` (`ActivityBase`, plus a new `ActivityReportSettings`)
- Modify: `backend/tests/conftest.py` (add the `db` and `clean_db` fixtures)
- Test: `backend/tests/test_item_roles.py`

**Interfaces:**
- Produces:
  - `Activity.report_role: str | None` (`String(32)`, nullable; `None` means use the default)
  - `Activity.hidden_pages: list[str] | None` (`JSON`, nullable)
  - `schemas.ActivityReportSettings(report_role: Optional[str], hidden_pages: Optional[list[str]])`
  - conftest fixtures: `db` (a `SessionLocal()` session that is closed after the test) and `clean_db`, which deletes all rows from `mood_activity_details`, `mood_activities`, `moods`, `activities`, `categories`, `garmin_sleep_daily`, `garmin_hrv_daily`, `garmin_stress_daily`, `garmin_resting_heart_rate_daily`, `garmin_steps_daily` and `garmin_activities` before the test

- [ ] **Step 1: Write the failing test** `test_activity_has_report_columns(signed_in, clean_db, db)`. It creates a category and an activity through `POST /categories/` and `POST /activities/`, then asserts that `GET /activities/{id}` JSON has `report_role is None` and `hidden_pages is None`.
- [ ] **Step 2:** Run `pytest tests/test_item_roles.py -q`. Expected: FAIL (KeyError `report_role`).
- [ ] **Step 3:** Add the two columns to the model, the `ALTER TABLE activities ADD COLUMN report_role VARCHAR(32)` and `... ADD COLUMN hidden_pages JSON` fallbacks (same pattern as `ignore_in_reports`), and `report_role: Optional[str] = None` and `hidden_pages: Optional[list[str]] = None` on `ActivityBase`.
- [ ] **Step 4:** Run the test. Expected: PASS. Run the full suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat(db): add report_role and hidden_pages to activities`

---

### Task 2: Item roles service and endpoint

**Files:**
- Create: `backend/app/services/item_roles.py`
- Modify: `backend/app/routes/activities.py` (new endpoint)
- Test: `backend/tests/test_item_roles.py`

**Interfaces:**
- Produces (in `item_roles.py`):
  - `ROLES = ("possible_cause", "describes_night", "symptom", "reaction", "habit")`
  - `EXCLUDING_ROLES = {"describes_night", "symptom", "reaction", "habit"}`
  - `LIFESTYLE_PAGE = "lifestyle_impact"`
  - `default_role_for_category(category_name: str | None) -> str`. Case-insensitive and trimmed: `"during sleep"` and `"morning / waking feedback"` give `describes_night`; `"headache issues"` gives `symptom`; everything else, including `None`, gives `possible_cause`.
  - `effective_role(activity: models.Activity) -> str`. Order: `report_role` if set; else `"habit"` if `ignore_in_reports`; else the category default.
  - `role_was_set_by_owner(activity) -> bool`. True if `report_role` is set or `ignore_in_reports` is true.
  - `is_hidden_on(activity, page: str) -> bool`
  - `is_before_sleep(category_name: str | None) -> bool` (`"before sleep"`, case-insensitive)
- Produces (endpoint): `PUT /activities/{activity_id}/report-settings`. The body is `ActivityReportSettings`. Only fields that are sent are applied (`model_fields_set`). The response is `ActivityResponse`. A `report_role` that isn't in `ROLES` (and isn't `null`) returns 422. **Keep the headache report in step:** after applying the change, set `ignore_in_reports = report_role in EXCLUDING_ROLES`. Clearing the role (`null`) sets `ignore_in_reports = False`.

- [ ] **Step 1: Write the failing tests:**
  - `test_default_roles_follow_category`: asserts that `"Before Sleep"` and `"Lifestyle"` give possible_cause, `" during sleep "` gives describes_night, `"Morning / Waking Feedback"` gives describes_night, `"Headache Issues"` gives symptom, and `None` gives possible_cause.
  - `test_ignored_activity_counts_as_habit`: `Activity(ignore_in_reports=True, report_role=None)` gives `"habit"`.
  - `test_owner_role_beats_default`: `report_role="reaction"` in a Before Sleep category gives `"reaction"`.
  - `test_set_role_via_api_also_sets_ignore_flag(signed_in, clean_db)`: a PUT of `{"report_role":"habit"}` gives `report_role=="habit"` and `ignore_in_reports is True`. A PUT of `{"report_role": null}` gives `report_role is None` and `ignore_in_reports is False`.
  - `test_hide_on_page_via_api`: a PUT of `{"hidden_pages":["lifestyle_impact"]}` is saved and `report_role` is unchanged.
  - `test_unknown_role_rejected`: a PUT of `{"report_role":"banana"}` returns 422.
- [ ] **Step 2:** Run them. Expected: FAIL (import error or 404).
- [ ] **Step 3:** Implement the module and the endpoint.
- [ ] **Step 4:** Run them. Expected: PASS. Run the full suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat: item report roles with category defaults and settings endpoint`

---

### Task 3: Matching entries to nights

**Files:**
- Create: `backend/app/services/insight_dates.py`
- Test: `backend/tests/test_insight_dates.py`

**Interfaces:**
- Produces:
  - `UK_TZ = ZoneInfo("Europe/London")`
  - `night_for_entry(logged_at: dt.datetime, before_sleep: bool) -> dt.date`. Returns the Garmin sleep date (the morning of waking) of the night the entry affects. Convert to UK time, take the date `d`. If `before_sleep` and the local hour is before 12, use `d - 1`. Return that date + 1.
  - `night_for_workout(start_time: dt.datetime) -> dt.date`. The UK local date + 1.
  - `is_late_workout(start_time: dt.datetime) -> bool`. True if the UK local hour is 18 or later.

- [ ] **Step 1: Write the failing tests** (tz-aware UTC inputs):
  - Fri 2026-10-09 21:30 UTC (22:30 BST), before_sleep: 2026-10-10
  - Fri 2026-10-09 23:30 UTC (00:30 BST Sat), before_sleep: 2026-10-10 (Review Focus 1)
  - Sat 2026-11-07 09:00 UTC (GMT), before_sleep: 2026-11-07 (logged late the next morning)
  - Sat 2026-11-07 09:00 UTC, before_sleep False: 2026-11-08
  - `night_for_workout` at 2026-10-12 17:30 UTC (18:30 BST): 2026-10-13. `is_late_workout` of it: True. 2026-10-12 16:30 UTC: False.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat: night matching rules for insights (midday rule, Garmin wake date)`

---

### Task 4: With/without comparison and confidence

**Files:**
- Create: `backend/app/services/comparison.py`
- Test: `backend/tests/test_comparison.py`

**Interfaces:**
- Produces:
  - `MIN_NIGHTS = 5`
  - `CONFIDENCE_ORDER = {"strong": 0, "some": 1, "weak": 2}`
  - `@dataclass class Comparison: with_n: int; without_n: int; with_mean: float | None; without_mean: float | None; effect: float | None; p_value: float | None; confidence: str` (`"strong" | "some" | "weak" | "too_early"`)
  - `compare(with_values: list[float], without_values: list[float], *, iterations: int = 2000, seed: int = 0) -> Comparison`
  - `is_negligible(effect: float, all_values: list[float]) -> bool`. True when `abs(effect) < 0.2 * statistics.pstdev(all_values)`, or when the standard deviation is 0.

**Method (decided here, as the spec left it to the builder):** this is a permutation test. Shuffle all the nights together with `random.Random(seed)`, split them into groups the same size as the real ones, and count how often the shuffled gap in means is at least as large (in absolute value) as the real gap. `p = (count + 1) / (iterations + 1)`.
- `too_early` if either side has fewer than `MIN_NIGHTS` nights. In that case `effect`, `p_value` and the means are `None`.
- `strong` if p < 0.05 and both sides have at least 8 nights.
- `some` if p < 0.20.
- `weak` otherwise.

The one-sentence explanation for the page: "Confidence is how rarely a gap this big turns up when your nights are shuffled at random."

- [ ] **Step 1: Write the failing tests:**
  - `test_too_early_below_five`: 4 with and 20 without gives `too_early` and `effect is None`.
  - `test_clear_difference_is_strong`: 10 values around 60 (`[58,60,61,59,62,60,57,61,60,59]`) against 10 around 75 gives `strong` and `effect == pytest.approx(-15.2, abs=0.01)`, which is the with mean minus the without mean.
  - `test_no_difference_is_weak`: identical spread on both sides gives `weak`.
  - `test_deterministic`: two calls give equal `p_value`.
  - `test_negligible`: `is_negligible(0.5, [60,70,80,90])` is True; `is_negligible(10, [60,70,80,90])` is False; all values equal gives True.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat: with/without comparison with permutation-test confidence`

---

### Task 5: Rewrite the Lifestyle Impact endpoint

**Files:**
- Modify: `backend/app/routes/lifestyle_impact.py` (replace `get_lifestyle_impact`, `_METRIC_CONFIG`, `_mark_highest`)
- Test: `backend/tests/test_lifestyle_impact.py`

**Interfaces:**
- Consumes: Tasks 2, 3 and 4.
- Produces: `GET /lifestyle-impact?metric=…&days=28|84|182&end_date=YYYY-MM-DD` (`end_date` is optional and defaults to today in UK time; tests use it). `days` must be one of 28, 84 or 182, otherwise 422. Function `get_lifestyle_impact(metric: str, days: int, db: Session, end_date: dt.date | None = None) -> dict`. The response:
  ```json
  {
    "metric": "sleep_score", "metric_label": "Sleep score", "higher_is_better": true,
    "period_label": "6 Oct - 2 Nov", "avg_value": 72.4, "nights_analysed": 26,
    "items": [{"activity_id": 12, "activity": "Alcohol", "effect": -11.2,
               "with_nights": 8, "without_nights": 18, "confidence": "strong",
               "better": false, "logged_with": []}],
    "too_early": [{"activity_id": 30, "activity": "Caffeine after 4pm", "with_nights": 3}],
    "left_out": [{"activity_id": 7, "activity": "Meditation", "reason": "habit"}],
    "min_nights": 5
  }
  ```
  `activity_id` is `null` for the workout entries. `reason` is the role name, or `"hidden"` for a hide on this page only. `better` is `(effect > 0) == higher_is_better`. `logged_with` lists other analysed items that have exactly the same set of "with" nights (twins).

- [ ] **Step 1: Write the failing tests.** Build the data with the `db` fixture, using made-up dates in Oct–Nov 2026 and `end_date=2026-11-30`. Each test inserts categories "Before Sleep", "During Sleep" and "Lifestyle", activities, moods with UTC timestamps, and Garmin rows.
  - `test_evening_item_matched_to_following_night`: "Alcohol" logged at 22:00 on 8 evenings. On each following `sleep_date` the score is 60; on the other 12 nights with a Before Sleep entry ("Reading") it is 78. The night *before* each drink has a score of 85, which is the trap the old code fell into. Expect Alcohol in `items` with `effect < 0` and `better is False`.
  - `test_unlogged_evening_is_not_a_without_night`: 6 alcohol nights and 6 nights with only Reading. 10 further nights have Garmin data but no Before Sleep entry at all. Expect `without_nights == 6`.
  - `test_night_items_and_habits_left_out`: "Woke During Night" (During Sleep) is absent from all three lists. "Meditation" with `report_role="habit"` is in `left_out` with reason `habit`. An item with `ignore_in_reports=True` is in `left_out` with reason `habit`. An item with `hidden_pages=["lifestyle_impact"]` has reason `hidden`.
  - `test_too_early_group`: an item on 3 nights appears in `too_early` with `with_nights == 3`.
  - `test_confidence_before_size`: item A has a small, consistent effect over 10 nights (strong). Item B has a large, noisy effect over 5 nights (weak or some). Expect A to be listed before B.
  - `test_negligible_effect_dropped`: an item whose nights equal the average isn't in `items`.
  - `test_hrv_uses_last_night`: `weekly_avg=70` on every row, with `payload={"hrvSummary":{"lastNightAvg":X}}` varying. Expect the effect to follow `lastNightAvg`.
  - `test_stress_uses_sleep_stress_or_falls_back`: with `dailySleepDTO.avgSleepStress` present on most nights, expect `metric_label == "Overnight stress"`. With it absent on all nights and `GarminStressDaily` rows present, expect `metric_label == "Stress"`.
  - `test_steps_use_next_day`: an evening item on day D is compared with `steps_date` D+1.
  - `test_workouts_included`: `GarminActivity` rows on 6 days (3 starting at 19:00 local). Expect a "Workout" entry with `activity_id is None` and `with_nights == 6`, and a "Late workout (after 6pm)" entry in `too_early` with 3.
  - `test_missing_fields_and_empty_period` (Review Focus 3 and 4): `sleep_score=None` rows are skipped. A period with no Garmin data returns 200 with empty lists and `avg_value is None`.
  - `test_same_item_twice_counts_once` (Review Focus 5): two mood entries on one evening both carrying Alcohol count as one "with" night.
  - `test_seven_days_rejected`: `days=7` returns 422.
  - `test_twins_flagged`: two items always logged together each list the other in `logged_with`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3: Implement.** Decisions the tests don't spell out:
  - **Measure by night (keyed by `sleep_date`, or by the Garmin date for the others):**
    - sleep_score: `GarminSleepDaily.sleep_score`
    - overnight_hrv: `GarminHRVDaily.payload["hrvSummary"]["lastNightAvg"]`, falling back to the key `lastNightAverage`, then to a top-level `lastNightAvg`
    - overnight_stress: `GarminSleepDaily.payload["dailySleepDTO"]["avgSleepStress"]`. If fewer than half the sleep nights in the window have it, use `GarminStressDaily.overall_stress_level` instead and set `metric_label` to "Stress".
    - resting_heart_rate: `GarminRestingHeartRateDaily.resting_heart_rate`
    - steps: `GarminStepsDaily.total_steps`
    - `higher_is_better` is False for stress and resting heart rate.
  - **Which moods to query:** from `start - 2 days` to `end + 1 day`, then keep only nights inside the window.
  - **"Logged tabs" per night:** the set of category ids with any entry mapped to that night. An item's "without" nights are the nights where its category was logged and the item wasn't, and where the measure has a value. Its "with" nights are the nights where it was logged and the measure has a value.
  - **Which items are analysed:** only items with `effective_role == "possible_cause"`, not hidden on `LIFESTYLE_PAGE`, and logged at least once in the window. `left_out` only includes items where `role_was_set_by_owner` is true or that are hidden on this page. Default night and symptom items stay silent.
  - **Workouts** come from `GarminActivity` with `night_for_workout`. Their "without" nights are every other night that has a measure value; no unknown nights. They are labelled "Workout" and "Late workout (after 6pm)".
  - **Drop** items where `is_negligible(effect, all_window_values)` is true, unless the confidence is `too_early` (those go to `too_early`).
  - **Sort** `items` by `(CONFIDENCE_ORDER[confidence], -abs(effect))`.
  - **Rounding:** `effect` to 1 decimal place (0 for steps). `avg_value` to 1 decimal place.
- [ ] **Step 4:** Run them. Expected: PASS. Run the full suite. Expected: all pass.
- [ ] **Step 5: Commit** `fix: lifestyle impact matches items to the right night and reports confidence`

---

### Task 6: Daily advice uses only confident results

**Files:**
- Modify: `backend/app/routes/lifestyle_impact.py` (`get_daily_advice`)
- Test: `backend/tests/test_lifestyle_impact.py`

**Interfaces:**
- Consumes: `get_lifestyle_impact(metric="sleep_score", days=84, db=db)` from Task 5.
- Produces: `GET /lifestyle-impact/advice` returning `{"advice": str}`, with the same shape as now.

The copy is fixed. Pick the first item (in list order) whose confidence is `strong` or `some`, and leave out workouts:
- if it's harmful (`better` false): `"Your last sleep score was {score}. On nights after {item}, your sleep score has been about {abs(effect):.0f} points lower. Worth skipping it tonight."`
- if it helps: `"Your last sleep score was {score}. On nights after {item}, your sleep score has been about {effect:.0f} points higher. Worth making time for it tonight."`
- If no item qualifies, keep the current fallback messages unchanged.

- [ ] **Step 1: Write the failing tests:**
  - `test_advice_warns_about_confident_harm`: with the alcohol data from Task 5, the advice contains "Alcohol" and "skipping".
  - `test_advice_ignores_weak_results`: with only too-early or weak items, the advice equals one of the existing fallback strings.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them. Expected: PASS. Run the full suite. Expected: all pass.
- [ ] **Step 5: Commit** `fix: daily advice only cites results with real evidence`

---

### Task 7: Rebuild the Lifestyle Impact page

Use the Impeccable skill. This is a visual change, so the owner must check it on the preview before it goes live.

**Files:**
- Modify: `frontend-web/src/routes/garmin-lifestyle-impact/+page.svelte`
- Modify: `frontend-web/src/tokens.css` (add `--color-better: #2a7d4f; --color-worse: #b23b3b; --color-confidence: #5b8fd0; --color-confidence-off: #e3ebf6;`)
- Modify: `README.md` line 59 (describe the new behaviour in one sentence)

**Interfaces:**
- Consumes: the Task 5 response, and `PUT /activities/{id}/report-settings` (Task 2) through `putJson` from `$lib/api`.

The behaviour comes from the agreed mockup (option B, version 2) and the spec's "Lifestyle Impact page" section:
- Period tabs: `4w` (28, default), `12w` (84) and `26w` (182). The measure tabs stay; show `metric_label` from the response.
- One list titled "What seems to affect your {metric_label lowercased}". Each row shows the name; the effect formatted with a sign plus a unit (`points` for sleep score, `ms` for HRV, `bpm` for resting heart rate, `steps` for steps, nothing for stress) and coloured by `better` using `--color-better` or `--color-worse`; "{with} nights with, {without} without"; a 3-segment meter (strong 3, some 2, weak 1) and its word ("Strong", "Some evidence", "Weak"); and the ⋯ button, only when `activity_id` isn't null.
- If an item has a non-empty `logged_with`, the row also says "Always logged with {names}, so the app can't separate them".
- The ⋯ menu opens inline under the row and asks "What is {name} for you?". Its options, in order, send these PUT bodies:
  - "Just a habit I'm recording": `{report_role:"habit"}`
  - "Describes how the night went": `{report_role:"describes_night"}`
  - "Something I do because of a symptom": `{report_role:"reaction"}`
  - "Hide from this page only": `{hidden_pages:[...existing, "lifestyle_impact"]}` (read the existing list from `GET /activities/{id}` first)

  After a successful PUT, reload the data. On failure, show the error in the existing status message.
- The "Too early to tell" section shows "{name}: {n} nights so far, needs at least {min_nights}".
- The "Left out of this page" section shows chips "{name} · {reason in words}" with ×. The × sends `{report_role:null}`, or removes `"lifestyle_impact"` from `hidden_pages` when the reason is `hidden`, then reloads.
- A footer note gives two plain sentences: the confidence sentence from Task 4, plus "During Sleep and Morning items describe the night, so they aren't listed here."
- Mobile: the list is one column. The ⋯ menu must be fully visible at 375px width.

- [ ] **Step 1:** Implement the page and the tokens.
- [ ] **Step 2:** Run `cd frontend-web && npm run check && npm run build`. Expected: 0 errors, and the build succeeds.
- [ ] **Step 3:** Start `scripts/preview.sh up`, open Lifestyle Impact and check, in this order:
  1. Each of the five tabs loads.
  2. 4w, 12w and 26w all load.
  3. Mark a test item as a habit through ⋯, and see it move to "Left out".
  4. Bring it back with ×.
  5. Repeat on a 375px-wide viewport.

  Take screenshots of the sleep score and stress tabs at desktop and phone widths. Note whether alcohol and caffeine now point the way the owner expects. Report what was seen, not a guess.
- [ ] **Step 4: Commit** `feat(ui): ranked lifestyle impact list with confidence and in-place item roles`

---

### Task 8: Review and hand-over

- [ ] **Step 1:** Run the full backend suite and the frontend check and build. Paste the output.
- [ ] **Step 2:** Run the `differential-review` skill on `main...feature/trustworthy-insights`, and report the findings by severity. Fix them on the branch.
- [ ] **Step 3:** Push the branch (`git push -u origin feature/trustworthy-insights`) and open a pull request. The description includes the changelog entry and change record, the screenshots, and the line `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Don't merge. The owner merges on GitHub after trying the preview.

## Rollout

- **Before merging:** take a production database backup on the NUC:
  `docker exec sleep_db pg_dump -U sleepuser sleepdb > backup_$(date +%Y%m%d_%H%M%S).sql`
  The two new columns are added automatically when the app starts (`_ensure_legacy_schema_compatibility`). Nothing is removed.
- No `.env` changes.
- This is a visual change, so it waits until the owner is home to check the preview, under the global rules.
- To undo: revert the merge. The extra columns are harmless if left in place.
