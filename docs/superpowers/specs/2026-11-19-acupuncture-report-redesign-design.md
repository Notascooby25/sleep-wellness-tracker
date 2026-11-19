# Acupuncture & Symptom Report Redesign — Design Document

**Date:** 2026-11-19  
**Status:** Draft (pending builder check and owner approval)  
**Target surface:** `frontend-web/src/routes/acupuncture-report/+page.svelte` and `backend/app/services/symptom_report.py` / `backend/app/routes/reports.py`

---

## 1. Intent & Why

The Acupuncture & Symptom Report is used primarily as a **quick-glance reference during acupuncture appointments** (frequently on a phone). When sitting with the acupuncturist, the owner needs two distinct answers quickly:

1. **Since the last appointment, how have headaches been?** How many symptom days out of how many days, which specific headache-category activities happened (`Headache – 7`, `Migraine – 3`, etc., without clutter from unselected items), where on the head they occurred (position tags), and when they clustered across the period.
2. **Are there real common triggers, or does it just look like bad luck / random?** Separate genuine day-before / biometric / same-day patterns from statistical noise, without letting short 2–3 week inter-appointment windows starve the statistics.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- **Fast, scannable clinic brief** at the top of the page showing the selected appointment period immediately.
- **Keep existing timeframe controls**: Start Date, End Date, and the “Quick Select Session” dropdown (`Since <date>`) for previous acupuncture sessions, with UK local timezone handling fixed so session dates never drift by a day.
- **Headache activity breakdown**: Show every activity in the Headache Issues category (or with effective role `symptom`) logged on at least 1 day in the period, counting distinct days, sorted highest first, hiding anything with zero.
- **Headache position breakdown**: Show every position tag (from `MoodActivityDetail.position`) logged on symptom activities in the period, counting distinct days, sorted highest first, hiding anything with zero.
- **Day-by-day visual calendar strip**: Visually show every day in the selected period (clear vs. headache vs. migraine, plus acupuncture session markers if any fall inside the window) so clusters and clear runs are obvious at a glance.
- **Comparison against the prior period**: Show a subtle delta pill on Frequency (e.g. `↓ from 52%`) comparing against the previous session gap (when viewing a session) or the immediately preceding equal-length period (when using custom dates), omitted cleanly when there is no prior data.
- **Sound, trustworthy trigger analysis** on an independent window (`This period` | `90 days` [default] | `All time`), clearly stating whether any real clues stood out or whether headaches look mostly random so far.
- **Fix all audited logic bugs** in `backend/app/services/symptom_report.py` and `backend/app/routes/reports.py`.

### Non-Goals
- No database schema changes or migrations.
- No new frontend or backend dependencies (pure HTML/CSS/SVG using existing `tokens.css`).
- No changes to how mood entries, activities, categories, or Garmin syncs are logged or stored.
- No PDF/print export flow (screen-first quick glance on phone and desktop).
- Do not break existing consumers of `GET /reports/headache-summary`.

### Anti-Goals (what would make this a failure even if it technically works)
- Showing zero-count headache types or zero-count positions that clutter the clinic summary.
- Presenting weak `0%` / `+2%` random coincidences as if they were real triggers.
- Making the top appointment summary wait on slow all-time statistical permutations before appearing.
- Treating evening “Before Sleep” activities as same-day triggers for earlier headaches, or showing items marked as `reaction` (“something I do because of a symptom”) as triggers.
- Violating the “Quiet Sanctuary” design language (no drop shadows, no harsh pure black/white backgrounds, no raw hex blues outside `tokens.css`).

---

## 3. Constraints

- **Stack:** FastAPI + SQLAlchemy 2.0+ + PostgreSQL (backend); Svelte 5 / SvelteKit (frontend); raw CSS with semantic tokens from `frontend-web/src/tokens.css`.
- **Design system:** `DESIGN.md` (“The Quiet Sanctuary”): flat cards (`#ffffff`, `1px solid var(--color-neutral-border)`, `12px` radius, zero drop shadows), soft blue/slate hierarchy, responsive collapse below `860px` with comfortable mobile touch targets (min 44px for interactive controls).
- **Security & privacy:** Public GitHub repo — never commit personal data, IPs, hostnames, or secrets. All `/reports/*` endpoints stay behind the existing application auth and proxy (`frontend-web/src/routes/api/[...path]/+server.ts`).
- **Backwards compatibility:** Existing `GET /reports/headache-summary` remains functional and preserves existing keys (plus backwards-compatible `triggers` alias).
- **Testing:** Backend tests must pass against a real PostgreSQL instance (`TEST_DATABASE_URL=... pytest tests -q`), including regression tests for every logic bug fixed. Frontend must pass `npm run check`, `npm run build`, and existing JS tests.

---

## 4. Approaches Considered

### Approach 1 — Two Independent Report Endpoints + Pure CSS/SVG Svelte UI *(Selected)*
- Split the backend computation into two clean services and endpoints:
  - `GET /reports/headache-appointment-summary?start_date=...&end_date=...` — fast, lightweight query returning stats, previous-period comparison, day-by-day timeline, symptom breakdown, and position breakdown.
  - `GET /reports/headache-triggers?window=90d|all|period&start_date=...&end_date=...` — runs the statistical trigger & Garmin biometric comparison independently.
  - Keep `GET /reports/headache-summary` working as a backwards-compatible endpoint built on the updated logic.
- Frontend fetches both in parallel on initial load; changing session/dates only reloads the fast top summary (unless trigger window is set to `This period`), and switching the trigger window (`This period` | `90 days` | `All time`) only reloads the bottom trigger card.
- **Tradeoff:** One extra endpoint to maintain, in exchange for instant clinic-brief loading and flicker-free switching between session dates and trigger windows.

### Approach 2 — Single Combined Endpoint *(Not selected)*
- Extend `GET /reports/headache-summary` with a `trigger_window` parameter and return everything in one payload.
- **Tradeoff:** Simpler API surface, but every date tweak or trigger-window toggle blocks the whole page on the full statistical permutation run (especially noticeable on `All time`).

### Approach 3 — Third-Party Charting Library *(Rejected)*
- Add Chart.js or similar for visuals.
- **Tradeoff:** Unnecessary dependency for a day-by-day strip and proportional horizontal bars; harder to match `tokens.css` cleanly and breaks the repo’s zero-chart-library simplicity.

---

## 5. Decided Design Details

### 5.1 Layout & Visuals (“Option A · Clinic Brief”)
1. **Header & Timeframe Bar**
   - Page heading (`Acupuncture & Symptom Report`) and subtitle.
   - Compact timeframe card with:
     - **Quick Select Session** dropdown (`Since <session date>` for each logged acupuncture session strictly before today, defaulting on load to the day after the most recent session strictly before today through today; or last 30 days if no prior acupuncture session exists). *(Our call: if you already logged today’s appointment before opening the report, initial load skips today’s session and shows the gap since the previous appointment instead of an empty 0-day window. If a user manually enters `start_date > end_date`, the frontend shows a clear inline message and the backend rejects it with HTTP 400.)*
     - **Start Date** and **End Date** native date inputs.
2. **Appointment Summary Card (top, loads independently & fast)**
   - **Stat Strip (3 boxes, plus optional 4th Avg Severity box only if non-null):**
     - `Symptom Days`
     - `Total Days`
     - `Frequency` (percentage) with a subtle comparison pill underneath (e.g. `↓ from 52%` / `↑ from 30%` / `same as prior`).
     - *(Our call on prior-period rules: if `start_date - 1 day` matches the most recent acupuncture session before `start_date`, no newer acupuncture session falls inside `[start_date, end_date)`, and an earlier session `prev_session` exists, compare against the previous session gap `[prev_session + 1 day, anchor_session]` inclusive of the anchor session day. Otherwise — custom dates, multi-session spans, or the earliest session — compare against the immediately preceding equal-length calendar window `[start_date - total_days, start_date - 1 day]`. Omit the pill cleanly if the prior window has zero logged mood entries, so pre-app/unlogged history never shows a misleading `from 0%`.)*
   - **Day-by-Day Timeline Strip (“When symptoms happened”):**
     - One cell per day in `[start_date, end_date]`.
     - States: **Clear** (soft neutral surface), **Headache / Symptom** (warm amber wash), **Migraine** (muted coral/red wash — any day where a logged symptom activity’s name contains `"migraine"`, case-insensitive; takes visual precedence if both headache and migraine were logged on the same day).
     - Optional subtle marker on days where an Acupuncture session was logged inside the range.
     - Compact legend underneath (`Clear`, `Headache`, `Migraine`, plus `Acupuncture` only if present in range).
     - Interactive hover/tap detail (native title + accessible tap-to-inspect line on mobile) showing the exact date, which headache activities were logged, and any positions logged that day.
   - **Two Side-by-Side Breakdown Columns (stack to 1 column on narrow screens):**
     - **Headache Types:** Horizontal proportional bars for each headache/symptom activity logged on `>= 1` distinct day in the period, showing name + distinct day count (e.g. `Headache · 7`, `Migraine · 3`), sorted highest count first, alphabetical tie-break. Activities with `0` days are omitted. Deprecated and current copies of the same activity name are merged via `_group_old_and_current_copies`.
     - **Positions Logged:** Horizontal proportional bars for each position tag (parsed via JSON/string normalization matching `backend/app/routes/mood.py`) logged on symptom activities in the period, counting distinct days per position, sorted highest count first. Zero-count positions are omitted. If no positions were logged in the period, this column is hidden cleanly and Headache Types spans full width.
3. **Possible Triggers Card (bottom, independent loading & window)**
   - **Header with segmented window toggle:** `This period` | `90 days` (default) | `All time`.
   - **Plain-English Verdict Banner:**
     - If one or more clear/possible clues (`strong` or `some` confidence and non-negligible effect) exist across day-before triggers, biometrics, or same-day factors: e.g. *“2 clues stood out across 84 logged days (31 headache days). Other tested factors looked random.”*
     - If enough data was tested (`>= 1` tested factor across activities, Garmin workouts, or Garmin biometrics, and `>= MIN_NIGHTS` symptom days) and **nothing** reached `some` or `strong`: e.g. *“No clear triggers stood out across 84 logged days (31 headache days) — so far, these look mostly random.”*
     - If too little data exists in the chosen window (e.g. `< MIN_NIGHTS` symptom days or `< MIN_NIGHTS` clean logged days): clearly explain there isn’t enough data in this window yet and suggest switching to `90 days` or `All time` (if currently on `This period`).
   - **Clue Lists (only `strong` or `some` confidence, non-negligible):**
     - **Day & night before (possible triggers):** activity or Garmin workout name, directional risk bar + signed `% headache risk`, `X days with, Y without`, twin note if always logged together, 3-bar confidence meter, and the `···` role/hide menu (for user activities) or watch badge (for Garmin workouts).
     - **Contributing biometrics (Garmin):** metric name, directional bar + signed diff with unit, symptom vs clean average, 3-bar confidence meter, watch badge.
     - **Same day (could be cause or reaction):** strictly non-`Before Sleep`, non-`reaction` items only, clearly separated with risk/frequency wording and role menu.
   - **Collapsible Secondary Sections (closed by default so noise stays out of sight):**
     - **Checked, no clear link (`N`):** includes user activities, Garmin workouts, and Garmin biometrics that met sample-size minimums (`>= 5` with and without) but had `weak` confidence or negligible effect. *(Our call on scope & deduplication: Garmin workouts/biometrics appear here with a watch badge and biometric diff/averages, and count toward the Verdict Banner’s tested-factor count. If an activity already appears as a clue in either `day_before` or `same_day`, suppress it from `no_clear_link` and `too_early` so the UI never contradicts itself. If an activity is weak/negligible in both `day_before` and `same_day`, show it once — preferring `day_before` — with its `···` role menu so the owner can still classify habits/reactions or hide it anytime.)*
     - **Too early to tell (`N`):** deduplicated list of user activities, Garmin workouts, and Garmin biometrics with `< MIN_NIGHTS` days so far, omitting any activity that was already evaluated in either `day_before` or `same_day`.
     - **Left out of this page (`N`):** chip list of items excluded via `habit`, `describes_night`, `reaction`, or `hidden` (owner overrides), each with one-click restore (`×`).

### 5.2 Audited Trigger & Data Logic Fixes (Backend)
1. **UK timezone consistency:**
   - `GET /reports/acupuncture-sessions` converts `Mood.timestamp` to `UK_TZ` (`Europe/London`) before calling `.date()`.
   - Frontend date arithmetic for “day after session” uses pure `YYYY-MM-DD` calendar math (never `new Date(iso)` + `toISOString()`, which can shift by a day across DST/timezones).
2. **Symptom & severity windowing:**
   - `symptom_severities` (and `symptom_breakdown`, `position_breakdown`, `daily_timeline`) ONLY include moods whose `UK_TZ` date falls strictly inside `[start_date, end_date]` (fixing the bug where entries from `start_date - 2 days` leaked into `average_severity`).
3. **Fair logged-day baseline for trigger analysis:**
   - Define `active_logged_days` within the trigger window as dates where the user logged at least one mood/activity entry (in `UK_TZ`).
   - For **activity triggers**, define `without_set` using active logged days in the window where the user logged on the relevant exposure day (`d - 1` for day-before, `d` for same-day) AND did not log the activity — rather than all calendar days — so blank/unlogged days do not fabricate false triggers, while optional activities (like alcohol or specific foods) are still compared fairly against all other active logging days.
   - For **symptom vs. clean days** inside trigger analysis (and biometrics), `clean_days` are `active_logged_days - symptom_days` (with Garmin biometrics still intersecting with days that have valid Garmin readings; hydration `0 ml` or missing remains unknown). Meanwhile, the top Appointment Summary still computes `Frequency = symptom_days / total_days` across real calendar days so “9 symptom days in 22 days” matches reality.
4. **Statistical filtering & multiple-testing correction:**
   - Apply Benjamini-Hochberg (`bh_adjust`) to **biometrics** as well as day-before and same-day activity candidates.
   - Filter out negligible effects:
     - For binary headache risk triggers: require `abs(effect_pct) >= 5` (at least a 5 percentage-point risk difference) AND `is_negligible(result.effect, outcome_vals)` is False.
     - For continuous biometrics: require `not is_negligible(result.effect, all_metric_vals)` and `round(diff, 1) != 0.0`.
   - Split evaluated items into **clear/possible clues** (`confidence in ("strong", "some")` and non-negligible) vs. **`no_clear_link`** (`weak` or negligible), rather than dumping weak/zero items into the main trigger list.
5. **Timing & role fixes:**
   - **`Before Sleep` activities** are tested ONLY in `triggers_day_before` (matched via `night_for_entry(mood.timestamp, True)`), NEVER in `triggers_same_day` (eliminating after-midnight double-counting and nonsensical evening-after-headache links).
   - **`reaction` role** (“Something I do because of a symptom”) is completely excluded from BOTH `triggers_day_before` and `triggers_same_day` (matching the UI promise “Never shown as a cause or trigger”) and appears in `left_out` with reason `"reaction"` so it can be restored anytime.
   - **Garmin workouts** use `night_for_workout(start_time)` when `start_time` is present (falling back to `activity_date + 1 day` only if `start_time` is null), fixing midnight workout date shifts.
   - **Garmin stress fallback**: if overnight `avgSleepStress` is absent/insufficient and fallback uses `GarminStressDaily`, shift by `+1 day` (`d - 1` affects `d`) and label accurately as `"Daytime Stress (day before)"` instead of mislabeling it `"Overnight Stress (night before)"`.
   - **Garmin HRV paths**: support the full 8 JSON lookup paths used by `lifestyle_impact.py`.
   - **Deduplicate `too_early`**: each activity appears at most once in `too_early` (keeping the highest `with_nights` count).

---

## 6. What’s Left to the Builder

- Exact CSS spacing, responsive grid column counts for the day-by-day strip on mobile vs. desktop, and compact rendering for very long ranges (e.g. `> 60` days: compact heat squares grouped or wrapped cleanly without horizontal overflow).
- Exact copy polish for verdict messages, tooltips, and accessible `aria-label`s.
- Exact JSON key naming for the new endpoints, provided all existing `GET /reports/headache-summary` keys remain backwards-compatible.
- Reusing or extracting shared position-normalization helpers (from `backend/app/routes/mood.py`) and shared Garmin metric extraction helpers if tidy.
- Full unit + Postgres integration tests covering every new feature and fixed logic bug, plus frontend verification (`npm run check`, `npm run build`, `page_check.mjs`, and visual preview screenshots).
