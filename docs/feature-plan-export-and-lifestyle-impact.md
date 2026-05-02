# Feature Plan: CSV Data Export & Lifestyle Impact Analysis

> **Date produced:** 2026-05-02
> **Repo:** Notascooby25/sleep-wellness-tracker

---

## Table of Contents

1. [Feature 1 – CSV Data Export](#feature-1--csv-data-export)
   - [Available Data Sources](#available-data-sources)
   - [Backend – Export Endpoint](#backend--export-endpoint)
   - [Frontend – Export Page](#frontend--export-page)
2. [Feature 2 – Lifestyle Impact Analysis](#feature-2--lifestyle-impact-analysis)
   - [Concept](#concept)
   - [The Algorithm](#the-algorithm)
   - [Backend – Lifestyle Impact Endpoint](#backend--lifestyle-impact-endpoint)
   - [Frontend – Lifestyle Impact Page](#frontend--lifestyle-impact-page)
3. [Summary of Files to Create / Modify](#summary-of-files-to-create--modify)
4. [Recommended Implementation Order](#recommended-implementation-order)

---

## Feature 1 – CSV Data Export

A new settings card links to `/settings/export`, where you select one or more **data sources**, a **date range**, and click Export to download a CSV file directly in the browser.

### Available Data Sources

| Label | Database Table |
|---|---|
| Mood Log | `moods` + `activities` (via `mood_activities`) |
| Sleep (Garmin) | `garmin_sleep_daily` |
| HRV (Garmin) | `garmin_hrv_daily` |
| Stress (Garmin) | `garmin_stress_daily` |
| Body Battery | `garmin_body_battery_daily` |
| Resting Heart Rate | `garmin_resting_heart_rate_daily` |
| Hydration | `garmin_hydration_daily` |
| Garmin Activities | `garmin_activities` |

---

### Backend – Export Endpoint

**File to create:** `backend/app/routes/export.py`

```
GET /export/csv
  ?sources=sleep,hrv,stress,mood   (comma-separated, one or more required)
  ?start_date=2025-01-01            (required)
  ?end_date=2025-05-02              (required)
```

**Logic:**

1. For each requested source, query the relevant table filtered by the date range.
2. Build a **merged-by-date** structure: one row per calendar date, with columns from all selected sources placed side by side.
3. Return as a `StreamingResponse` with:
   - `Content-Type: text/csv`
   - `Content-Disposition: attachment; filename=export_<start>_<end>.csv`

**Example column layout** (sleep + hrv + mood selected):

```
date, sleep_score, total_sleep_minutes, deep_sleep_minutes, rem_sleep_minutes,
awake_minutes, hrv_weekly_avg, hrv_status, mood_score, activities
```

For mood, all logged activities for that date are comma-joined into a single column (e.g. `"Running, Eye Mask"`).

**Registration:** Add the new router to `backend/app/main.py` alongside the existing routers.

---

### Frontend – Export Page

**File to create:** `frontend-web/src/routes/settings/export/+page.svelte`

**UI layout:**

```
┌─────────────────────────────────────────────────┐
│  Export Data to CSV                             │
│                                                 │
│  Date Range                                     │
│  From: [date picker]        To: [date picker]   │
│                                                 │
│  Data Sources  (multi-select checkboxes)        │
│  ☑ Sleep        ☑ HRV          ☑ Stress        │
│  ☑ Body Battery ☐ Resting HR   ☐ Hydration     │
│  ☐ Mood Log     ☐ Garmin Activities             │
│                                                 │
│              [ Export CSV ]                     │
└─────────────────────────────────────────────────┘
```

**On click behaviour:**
- Build the query string from the selected sources and date range.
- `fetch('/api/export/csv?...')` the endpoint.
- Receive the response as a `Blob`, create a temporary `<a>` element, set `href` to an object URL, and programmatically click it to trigger the browser download.
- No page navigation required.

**Settings card to add in `settings/+page.svelte`:**

```svelte
<a class="settings-link" href="/settings/export">
  <h3>Export Data</h3>
  <p>Download mood logs and Garmin data as a CSV for any date range.</p>
</a>
```

---

## Feature 2 – Lifestyle Impact Analysis

### Concept

Inspired by Garmin's own **Lifestyle Logging** screen (screenshots below description), this feature shows — for a selected wellness metric and time window — which logged activities **positively** or **negatively** correlated with that metric, ranked into impact bands.

**Supported metrics:**

| Metric label | Source column | Direction (better = ?) |
|---|---|---|
| Sleep Score | `garmin_sleep_daily.sleep_score` | Higher is better |
| Overnight HRV | `garmin_hrv_daily.weekly_avg` | Higher is better |
| Overnight Stress | `garmin_stress_daily.overall_stress_level` | Lower is better |

**Time windows:** 7 days (7d) · 4 weeks (4w) · 12 weeks (12w)

The app already has all the raw ingredients:
- `moods.timestamp` links activities (via `mood_activities`) to specific dates.
- The Garmin daily tables provide the metric values on those same dates.

---

### The Algorithm

For a given metric and date window:

1. Compute the **overall baseline average** across all dates in the window that have a metric reading.
2. For each **activity** logged in the window:
   - Find all dates it was logged.
   - Fetch the metric value for each of those dates.
   - Compute `delta = mean(metric on days WITH activity) − overall_mean`.
3. **Direction correction:**
   - For Sleep Score and HRV: a positive delta = positive impact.
   - For Stress: a negative delta = positive impact (lower stress is better). Invert the sign when classifying.
4. **Classify by adjusted delta:**
   - `adjusted_delta > +threshold` → **Positive Impact**
   - `adjusted_delta < -threshold` → **Negative Impact**
   - Otherwise → **Minimal Impact**
   - Mark the entry with the largest absolute delta as **"Highest Impact"** within each band.
5. **Minimum sample guard:** exclude any activity that appears on fewer than **3 dates** in the window to avoid spurious results from single occurrences.

> The `threshold` defaults to 5 % of the metric's standard deviation across the window. This can be tuned as more data accumulates.

---

### Backend – Lifestyle Impact Endpoint

**File to create:** `backend/app/routes/lifestyle_impact.py`

```
GET /lifestyle-impact
  ?metric=sleep_score | overnight_hrv | overnight_stress
  ?days=7 | 28 | 84
```

**Example response:**

```json
{
  "metric": "sleep_score",
  "period_label": "8 Feb – 2 May",
  "avg_value": 79,
  "positive_impact": [
    { "activity": "Eye Mask",              "delta": 6.2, "highest": true  },
    { "activity": "Ear Plugs/Headphones",  "delta": 3.1, "highest": false }
  ],
  "negative_impact": [
    { "activity": "Vigorous Exercise",     "delta": -8.4, "highest": true  },
    { "activity": "Illness",               "delta": -4.1, "highest": false }
  ],
  "minimal_impact": [
    { "activity": "Light Exercise",        "delta": 0.8,  "highest": false },
    { "activity": "Traveling/Vacation",    "delta": -0.5, "highest": false }
  ]
}
```

**Registration:** Add the new router to `backend/app/main.py`.

---

### Frontend – Lifestyle Impact Page

**File to create:** `frontend-web/src/routes/garmin-lifestyle-impact/+page.svelte`

**UI design** (matches Garmin aesthetic, uses your app's existing design language):

```
┌─────────────────────────────────────────────────┐
│  Lifestyle Impact                               │
│                                                 │
│  [  7d  ]  [  4w  ]  [  12w  ]                 │
│  ‹  8 Feb – 2 May                               │
│                                                 │
│  [ Overnight Stress ] [ Overnight HRV ] [ Sleep Score ]
│                                                 │
│  ┌───────────────────────────────┐              │
│  │   79   Avg Score              │              │
│  └───────────────────────────────┘              │
│                                                 │
│  ── Positive Impact ──────────────────          │
│  ┌───────────────────────────────┐              │
│  │  Eye Mask  ⓘ      Highest    │              │
│  └───────────────────────────────┘              │
│  ┌───────────────────────────────┐              │
│  │  Ear Plugs/Headphones  ⓘ     │              │
│  └───────────────────────────────┘              │
│                                                 │
│  ── Negative Impact ──────────────────          │
│  ┌───────────────────────────────┐              │
│  │  Vigorous Exercise  ⓘ  Highest│             │
│  └───────────────────────────────┘              │
│  ┌───────────────────────────────┐              │
│  │  Illness  ⓘ                  │              │
│  └───────────────────────────────┘              │
│                                                 │
│  ── Minimal Impact ───────────────────          │
│  ┌───────────────────────────────┐              │
│  │  Light Exercise  ⓘ           │              │
│  └───────────────────────────────┘              │
└─────────────────────────────────────────────────┘
```

**ⓘ tooltip (on hover):** Shows the human-readable delta, e.g.:
> *"On days you logged Eye Mask, your sleep score averaged +6.2 points above your baseline."*

**Nav link:** Add a link to this page in `frontend-web/src/routes/+layout.svelte` alongside the existing Garmin pages (e.g. next to "Garmin Log").

---

## Summary of Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `backend/app/routes/export.py` | **Create** | CSV export endpoint |
| `backend/app/routes/lifestyle_impact.py` | **Create** | Lifestyle impact analysis endpoint |
| `backend/app/main.py` | **Modify** | Register both new routers |
| `frontend-web/src/routes/settings/export/+page.svelte` | **Create** | Export UI in settings |
| `frontend-web/src/routes/garmin-lifestyle-impact/+page.svelte` | **Create** | Lifestyle impact UI |
| `frontend-web/src/routes/settings/+page.svelte` | **Modify** | Add "Export Data" settings card |
| `frontend-web/src/routes/+layout.svelte` | **Modify** | Add nav link to lifestyle impact page |

---

## Recommended Implementation Order

| Step | Feature | Reason |
|---|---|---|
| 1 | Backend export route | Self-contained; reuses existing `_serialize_*` functions from `garmin.py` |
| 2 | Frontend export page | Simple form, no new DB concepts, immediately useful |
| 3 | Backend lifestyle impact route | Meatiest piece — pure SQL aggregation, no DB schema changes needed |
| 4 | Frontend lifestyle impact page | Build once API shape is confirmed and tested |

> ⚠️ **Database reminder:** As stated in project conventions — whenever any DB migration or destructive operation is involved, **back up the database first** before applying changes.
