import datetime
import os
from collections import defaultdict
from zoneinfo import ZoneInfo

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://backend:8000")
UK_TZ = ZoneInfo("Europe/London")
DEFAULT_RANGE_DAYS = 30

st.set_page_config(page_title="Analytics", layout="wide")

st.markdown(
    """
<style>
:root {
    --bg-soft: #f4f7fb;
    --card-bg: #ffffff;
    --card-border: #d9e2ef;
    --text-main: #132238;
    --text-sub: #5f6f84;
}

[data-testid="stAppViewContainer"] {
    background:
      radial-gradient(900px 260px at 8% -12%, #dbeafe 0%, transparent 45%),
      radial-gradient(900px 280px at 92% -18%, #e5f4ff 0%, transparent 42%),
      linear-gradient(180deg, #f9fbff 0%, #f2f6fc 100%);
}

.block-container {
    max-width: 1180px;
    padding-top: 1.2rem;
    padding-bottom: 1.8rem;
}

.hero {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
    margin-bottom: 14px;
}

.hero h1 { margin: 0; color: var(--text-main); font-size: 1.8rem; line-height: 1.15; }
.hero p { margin: 8px 0 0; color: var(--text-sub); font-size: 0.96rem; }

.stat-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 0.9rem 1rem;
    box-shadow: 0 4px 12px rgba(30,58,138,0.05);
    text-align: center;
}
.stat-label { color: var(--text-sub); font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.stat-value { color: var(--text-main); font-size: 1.5rem; font-weight: 800; margin-top: 0.2rem; }
.stat-sub { color: var(--text-sub); font-size: 0.8rem; margin-top: 0.14rem; }

.section-heading {
    color: var(--text-main);
    font-size: 1.05rem;
    font-weight: 700;
    margin: 1.1rem 0 0.5rem;
    border-bottom: 1px solid var(--card-border);
    padding-bottom: 0.3rem;
}

.section-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.4rem;
}

@media (max-width: 860px) {
    .block-container { padding-left: 0.75rem; padding-right: 0.75rem; padding-top: 0.95rem; }
    .hero h1 { font-size: 1.5rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
    <h1>Analytics</h1>
    <p>Trends and insights across mood, sleep, and Garmin wellness data.</p>
</div>
""",
    unsafe_allow_html=True,
)


def section_header(title: str, help_text: str):
    title_col, help_col = st.columns([0.92, 0.08])
    with title_col:
        st.markdown(f"<div class='section-heading'>{title}</div>", unsafe_allow_html=True)
    with help_col:
        with st.popover("Info"):
            st.markdown(help_text)

# ── Date range controls ──────────────────────────────────────────────────────
today = datetime.datetime.now(UK_TZ).date()
default_start = today - datetime.timedelta(days=DEFAULT_RANGE_DAYS - 1)

range_col1, range_col2, range_col3 = st.columns([0.35, 0.35, 0.3])
with range_col1:
    start_date = st.date_input("From", value=default_start, max_value=today, key="analytics_start")
with range_col2:
    end_date = st.date_input("To", value=today, min_value=start_date, max_value=today, key="analytics_end")
with range_col3:
    preset = st.selectbox(
        "Quick range",
        options=["Custom", "Last 7 days", "Last 14 days", "Last 30 days", "Last 90 days"],
        index=3,
        key="analytics_preset",
    )

if preset != "Custom":
    days_map = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "Last 90 days": 90}
    preset_days = days_map[preset]
    start_date = today - datetime.timedelta(days=preset_days - 1)
    end_date = today

start_iso = start_date.isoformat()
end_iso = end_date.isoformat()
num_days = (end_date - start_date).days + 1

view_col1, view_col2 = st.columns([0.45, 0.55])
with view_col1:
    analytics_view_mode = st.radio(
        "Display",
        options=["Core", "Core + one extra"],
        horizontal=True,
        key="analytics_view_mode",
    )
with view_col2:
    extra_section = st.radio(
        "Extra section",
        options=["Recovery Metrics", "Mood Distribution", "Activity Log"],
        horizontal=True,
        key="analytics_extra_section",
        disabled=analytics_view_mode != "Core + one extra",
    )


# ── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_mood_all(start: str, end: str):
    try:
        r = requests.get(
            f"{API_BASE}/mood/",
            params={"from_date": start, "to_date": end},
            timeout=10,
        )
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


def normalize_iso_timestamp(value: str) -> str:
    ts = (value or "").strip()
    if ts.endswith("Z"):
        return ts[:-1] + "+00:00"
    return ts


def parse_entry_datetime_uk(entry: dict) -> datetime.datetime:
    ts = normalize_iso_timestamp(entry.get("timestamp", ""))
    return datetime.datetime.fromisoformat(ts).astimezone(UK_TZ)


@st.cache_data(ttl=600, show_spinner=False)
def load_garmin_range(metric_path: str, start: str, end: str):
    try:
        r = requests.get(
            f"{API_BASE}/garmin/{metric_path}/range",
            params={"start_date": start, "end_date": end},
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json().get("data") or []
        return {row["date"]: row for row in rows if isinstance(row, dict) and row.get("date")}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def load_activities_list():
    try:
        r = requests.get(f"{API_BASE}/activities/", timeout=4)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def load_categories_list():
    try:
        r = requests.get(f"{API_BASE}/categories/", timeout=4)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


mood_entries_all = load_mood_all(start_iso, end_iso)
sleep_rows = load_garmin_range("sleep", start_iso, end_iso)
body_rows = load_garmin_range("body-battery", start_iso, end_iso)
hrv_rows = load_garmin_range("hrv", start_iso, end_iso)
rhr_rows = load_garmin_range("resting-heart-rate", start_iso, end_iso)
activities_list = load_activities_list()
categories_list = load_categories_list()
activity_name_map = {a["id"]: a["name"] for a in activities_list if a.get("id")}
activity_cat_map = {a["id"]: a.get("category_id") for a in activities_list if a.get("id")}
category_name_map = {c["id"]: c["name"] for c in categories_list if c.get("id")}

# Identify sleep-relevant category IDs by name (case-insensitive substring match)
_SLEEP_CAT_KEYWORDS = ("before sleep", "during sleep", "presleep", "pre-sleep", "pre sleep")
sleep_cat_ids = {
    c["id"]
    for c in categories_list
    if c.get("name") and any(kw in c["name"].lower() for kw in _SLEEP_CAT_KEYWORDS)
}

# Filter mood entries to the selected date range
def entry_date_uk(entry) -> datetime.date | None:
    try:
        return parse_entry_datetime_uk(entry).date()
    except Exception:
        return None

mood_entries = [
    e for e in mood_entries_all
    if (d := entry_date_uk(e)) is not None and start_date <= d <= end_date
]

# Build daily mood aggregates
daily_mood: dict = {}
for entry in mood_entries:
    score = entry.get("mood_score")
    if score is None:
        continue
    try:
        dt_uk = parse_entry_datetime_uk(entry)
        day_str = dt_uk.date().isoformat()
    except Exception:
        continue
    daily_mood.setdefault(day_str, []).append(score)

daily_avg_mood = {d: sum(v) / len(v) for d, v in daily_mood.items()}

# ── Summary KPI cards ─────────────────────────────────────────────────────────
section_header(
    "Summary",
    "High-level snapshot for the selected date range: how many entries/sleep days you have, and average mood/sleep/recovery values.",
)

total_entries = len([e for e in mood_entries if e.get("mood_score") is not None])
rated_scores = [e["mood_score"] for e in mood_entries if e.get("mood_score") is not None]
avg_mood = sum(rated_scores) / len(rated_scores) if rated_scores else None
mood_label_map = {1: "Great", 2: "Good", 3: "Okay", 4: "Low", 5: "Rubbish"}

best_day_str = min(daily_avg_mood, key=daily_avg_mood.get) if daily_avg_mood else None
worst_day_str = max(daily_avg_mood, key=daily_avg_mood.get) if daily_avg_mood else None

sleep_scores_all = [r["sleep_score"] for r in sleep_rows.values() if r.get("sleep_score") is not None]
avg_sleep_score = sum(sleep_scores_all) / len(sleep_scores_all) if sleep_scores_all else None

sleep_mins_all = [r["total_sleep_minutes"] for r in sleep_rows.values() if r.get("total_sleep_minutes") is not None]
avg_sleep_mins = sum(sleep_mins_all) / len(sleep_mins_all) if sleep_mins_all else None

hrv_all = [r["weekly_avg"] for r in hrv_rows.values() if r.get("weekly_avg") is not None]
avg_hrv = sum(hrv_all) / len(hrv_all) if hrv_all else None

kpi_cols = st.columns(6)
stats = [
    ("Mood entries", str(total_entries), f"over {num_days} days"),
    ("Avg mood", f"{avg_mood:.1f}" if avg_mood else "—", mood_label_map.get(round(avg_mood), "") if avg_mood else ""),
    ("Sleep data days", str(len(sleep_rows)), f"of {num_days}"),
    ("Avg sleep", f"{int(avg_sleep_mins)//60}h {int(avg_sleep_mins)%60:02d}m" if avg_sleep_mins else "—", "per night"),
    ("Avg sleep score", f"{avg_sleep_score:.0f}/100" if avg_sleep_score else "—", f"{len(sleep_scores_all)} days"),
    ("Avg HRV", f"{avg_hrv:.0f}" if avg_hrv else "—", f"{len(hrv_all)} days"),
]
for col, (label, value, sub) in zip(kpi_cols, stats):
    with col:
        st.markdown(
            f"<div class='stat-card'>"
            f"<div class='stat-label'>{label}</div>"
            f"<div class='stat-value'>{value}</div>"
            f"<div class='stat-sub'>{sub}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

# ── Mood trend chart ──────────────────────────────────────────────────────────
if daily_avg_mood:
    section_header(
        "Mood Trend",
        "Daily average mood score over time. Lower is better: 1 is great, 5 is struggling.",
    )
    import pandas as pd

    all_days = [
        (start_date + datetime.timedelta(days=i)).isoformat() for i in range(num_days)
    ]
    mood_df = pd.DataFrame(
        {
            "Date": pd.to_datetime(all_days),
            "Avg Mood": [daily_avg_mood.get(d) for d in all_days],
        }
    )
    mood_df = mood_df.dropna()

    chart_col, info_col = st.columns([0.75, 0.25])
    with chart_col:
        st.line_chart(
            mood_df.set_index("Date")["Avg Mood"],
            y_label="Mood score (1=great, 5=rubbish)",
            use_container_width=True,
            height=220,
        )
    with info_col:
        if best_day_str:
            best_dt = datetime.date.fromisoformat(best_day_str)
            st.markdown(
                f"<div class='stat-card' style='margin-bottom:0.5rem'>"
                f"<div class='stat-label'>Best day</div>"
                f"<div class='stat-value' style='font-size:1.1rem'>{best_dt.strftime('%d %b')}</div>"
                f"<div class='stat-sub'>avg {daily_avg_mood[best_day_str]:.1f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        if worst_day_str:
            worst_dt = datetime.date.fromisoformat(worst_day_str)
            st.markdown(
                f"<div class='stat-card'>"
                f"<div class='stat-label'>Toughest day</div>"
                f"<div class='stat-value' style='font-size:1.1rem'>{worst_dt.strftime('%d %b')}</div>"
                f"<div class='stat-sub'>avg {daily_avg_mood[worst_day_str]:.1f}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
else:
    st.info("No mood data for this period.")

# ── Sleep + Mood correlation ──────────────────────────────────────────────────
sleep_and_mood_dates = sorted(set(sleep_rows.keys()) & set(daily_avg_mood.keys()))
if len(sleep_and_mood_dates) >= 3:
    section_header(
        "Sleep vs Mood",
        "Compares sleep score and sleep duration against daily mood. Use it to spot whether better sleep tends to line up with better mood.",
    )
    import pandas as pd

    sm_records = []
    for d in sleep_and_mood_dates:
        s = sleep_rows[d]
        sm_records.append(
            {
                "Date": pd.to_datetime(d),
                "Sleep score": s.get("sleep_score"),
                "Sleep duration (h)": round(s.get("total_sleep_minutes", 0) / 60, 1) if s.get("total_sleep_minutes") else None,
                "Avg mood": daily_avg_mood[d],
            }
        )
    sm_df = pd.DataFrame(sm_records).dropna(subset=["Avg mood"])

    chart_left, chart_right = st.columns(2)
    with chart_left:
        score_df = sm_df.dropna(subset=["Sleep score"]).set_index("Date")[["Sleep score", "Avg mood"]]
        if not score_df.empty:
            st.caption("Sleep score vs mood score")
            st.line_chart(score_df, use_container_width=True, height=200)
    with chart_right:
        dur_df = sm_df.dropna(subset=["Sleep duration (h)"]).set_index("Date")[["Sleep duration (h)", "Avg mood"]]
        if not dur_df.empty:
            st.caption("Sleep duration vs mood score")
            st.line_chart(dur_df, use_container_width=True, height=200)

# ── HRV + Body Battery trend ──────────────────────────────────────────────────
show_recovery = analytics_view_mode == "Core + one extra" and extra_section == "Recovery Metrics"
if show_recovery and (hrv_rows or body_rows):
    section_header(
        "Recovery Metrics",
        "Recovery-only panel. HRV trend and end-of-day body battery trend across the selected period.",
    )
    import pandas as pd

    all_days = [(start_date + datetime.timedelta(days=i)).isoformat() for i in range(num_days)]
    rec_df = pd.DataFrame(
        {
            "Date": pd.to_datetime(all_days),
            "HRV": [hrv_rows.get(d, {}).get("weekly_avg") for d in all_days],
            "Body Battery (EOD)": [body_rows.get(d, {}).get("end_of_day_value") for d in all_days],
        }
    )

    hrv_col, bb_col = st.columns(2)
    with hrv_col:
        hrv_data = rec_df.dropna(subset=["HRV"]).set_index("Date")[["HRV"]]
        if not hrv_data.empty:
            st.caption("HRV trend")
            st.line_chart(hrv_data, use_container_width=True, height=200)
        else:
            st.caption("No HRV data in this range.")
    with bb_col:
        bb_data = rec_df.dropna(subset=["Body Battery (EOD)"]).set_index("Date")[["Body Battery (EOD)"]]
        if not bb_data.empty:
            st.caption("End-of-day body battery trend")
            st.line_chart(bb_data, use_container_width=True, height=200)
        else:
            st.caption("No body battery data in this range.")

# ── Mood score distribution ───────────────────────────────────────────────────
show_distribution = analytics_view_mode == "Core + one extra" and extra_section == "Mood Distribution"
if show_distribution and rated_scores:
    section_header(
        "Mood Distribution",
        "How often each mood score appears, plus average mood by hour of day to highlight time-of-day patterns.",
    )
    import pandas as pd

    from collections import Counter
    score_counts = Counter(rated_scores)
    dist_df = pd.DataFrame(
        {
            "Mood": [mood_label_map.get(s, str(s)) for s in range(1, 6)],
            "Count": [score_counts.get(s, 0) for s in range(1, 6)],
        }
    ).set_index("Mood")

    dist_col, hod_col = st.columns(2)
    with dist_col:
        st.caption("How often each mood score was logged")
        st.bar_chart(dist_df, use_container_width=True, height=220)

    with hod_col:
        # Hour-of-day mood averages
        hour_scores: dict = defaultdict(list)
        for entry in mood_entries:
            score = entry.get("mood_score")
            if score is None:
                continue
            try:
                dt_uk = parse_entry_datetime_uk(entry)
                hour_scores[dt_uk.hour].append(score)
            except Exception:
                continue

        if hour_scores:
            hod_df = pd.DataFrame(
                {
                    "Hour": list(range(24)),
                    "Avg mood": [
                        round(sum(hour_scores[h]) / len(hour_scores[h]), 2) if h in hour_scores else None
                        for h in range(24)
                    ],
                }
            ).dropna().set_index("Hour")
            st.caption("Average mood by time of day")
            st.bar_chart(hod_df, use_container_width=True, height=220)

# ── Top activities ─────────────────────────────────────────────────────────────
show_activity_log = analytics_view_mode == "Core + one extra" and extra_section == "Activity Log"
if show_activity_log and mood_entries and activity_name_map:
    section_header(
        "Activity Log",
        "Most logged activities and the average mood score on entries where each activity was present.",
    )

    activity_count: Counter = Counter()
    activity_mood_scores: dict = defaultdict(list)

    for entry in mood_entries:
        acts = entry.get("activity_ids") or []
        score = entry.get("mood_score")
        for act_id in acts:
            name = activity_name_map.get(act_id, f"#{act_id}")
            activity_count[name] += 1
            if score is not None:
                activity_mood_scores[name].append(score)

    if activity_count:
        import pandas as pd

        top_n = 15
        top_acts = activity_count.most_common(top_n)
        act_df = pd.DataFrame(top_acts, columns=["Activity", "Occurrences"]).set_index("Activity")

        act_left, act_right = st.columns(2)
        with act_left:
            st.caption(f"Most logged activities (top {top_n})")
            st.bar_chart(act_df, use_container_width=True, height=280)

        with act_right:
            # Average mood when each activity was logged
            act_mood_rows = [
                {"Activity": name, "Avg mood when logged": round(sum(scores) / len(scores), 2)}
                for name, scores in activity_mood_scores.items()
                if len(scores) >= 2
            ]
            if act_mood_rows:
                mood_act_df = (
                    pd.DataFrame(act_mood_rows)
                    .sort_values("Avg mood when logged")
                    .set_index("Activity")
                )
                st.caption("Avg mood score when activity was logged (lower = better)")
                st.bar_chart(mood_act_df, use_container_width=True, height=280)

st.markdown("<br>", unsafe_allow_html=True)

# ── Before/During Sleep activities → sleep impact ─────────────────────────────
# Load a slightly wider window for sleep data so edge dates still match cleanly.
_sleep_ext_end = (end_date + datetime.timedelta(days=1)).isoformat()
sleep_rows_ext = load_garmin_range("sleep", start_iso, _sleep_ext_end)

# Build per-night activity sets for sleep-category entries.
# Entry logged on wakeup morning date D maps to Garmin sleep record date D.
night_activities: dict = defaultdict(set)  # {sleep_date_iso: {activity_name, ...}}

for entry in mood_entries_all:
    act_ids = entry.get("activity_ids") or []
    # Only entries that have at least one activity in a sleep category
    sleep_acts = [
        aid for aid in act_ids
        if activity_cat_map.get(aid) in sleep_cat_ids
    ]
    if not sleep_acts:
        continue
    entry_day = entry_date_uk(entry)
    if entry_day is None:
        continue
    # Entry logged on wakeup morning D matches the Garmin sleep record also dated D.
    sleep_date_iso = entry_day.isoformat()
    for aid in sleep_acts:
        night_activities[sleep_date_iso].add(activity_name_map.get(aid, f"#{aid}"))

# Only proceed if we have at least some annotated nights with matching sleep data
annotated_nights = {d: acts for d, acts in night_activities.items() if d in sleep_rows_ext}

if sleep_cat_ids and annotated_nights:
    import pandas as pd
    from collections import Counter

    section_header(
        "Before/During Sleep Activities & Sleep Quality",
        "Links activities logged in Before Sleep / During Sleep categories to that same morning's Garmin sleep record. "
        "'With' means nights where the activity was logged, and 'baseline' means nights where it was not logged.",
    )
    st.caption(
        "Each night where you logged Before Sleep or During Sleep activities is matched to "
        "the Garmin sleep data for that night. Averages are shown per activity — nights without "
        "that activity logged provide the baseline."
    )

    # Collect all unique activities appearing on tracked nights
    all_sleep_acts = sorted({a for acts in annotated_nights.values() for a in acts})

    # Build records: one row per annotated night with sleep metrics
    night_records = []
    for date_str, acts in annotated_nights.items():
        s = sleep_rows_ext.get(date_str, {})
        if not s:
            continue
        night_records.append({
            "date": date_str,
            "activities": acts,
            "total_h": round(s["total_sleep_minutes"] / 60, 2) if s.get("total_sleep_minutes") else None,
            "deep_h": round(s["deep_sleep_minutes"] / 60, 2) if s.get("deep_sleep_minutes") else None,
            "light_h": round(s["light_sleep_minutes"] / 60, 2) if s.get("light_sleep_minutes") else None,
            "rem_h": round(s["rem_sleep_minutes"] / 60, 2) if s.get("rem_sleep_minutes") else None,
            "score": s.get("sleep_score"),
        })

    if night_records:
        # Per-activity averages vs baseline (nights that activity was NOT logged)
        metrics = [
            ("Sleep score /100", "score"),
            ("Total sleep (h)", "total_h"),
            ("Deep sleep (h)", "deep_h"),
            ("REM sleep (h)", "rem_h"),
            ("Light sleep (h)", "light_h"),
        ]

        act_rows = []
        for act_name in all_sleep_acts:
            nights_with = [r for r in night_records if act_name in r["activities"]]
            nights_without = [r for r in night_records if act_name not in r["activities"]]
            if len(nights_with) < 1:
                continue
            row = {"Activity": act_name, "Nights logged": len(nights_with)}
            for label, key in metrics:
                with_vals = [r[key] for r in nights_with if r[key] is not None]
                without_vals = [r[key] for r in nights_without if r[key] is not None]
                row[f"{label} (with)"] = round(sum(with_vals) / len(with_vals), 1) if with_vals else None
                row[f"{label} (baseline)"] = round(sum(without_vals) / len(without_vals), 1) if without_vals else None
            act_rows.append(row)

        if act_rows:
            act_df = pd.DataFrame(act_rows)

            # ── Comparison table ──────────────────────────────────────────
            st.markdown("**Activity impact table** — *with* vs *baseline* (nights that activity wasn't logged)")
            display_cols = ["Activity", "Nights logged"] + [f"{l} (with)" for l, _ in metrics] + [f"{l} (baseline)" for l, _ in metrics]
            display_cols = [c for c in display_cols if c in act_df.columns]
            st.dataframe(
                act_df[display_cols].set_index("Activity"),
                use_container_width=True,
            )

            # ── Bar charts: sleep score and total duration ─────────────
            chart_acts = act_df.dropna(subset=["Sleep score /100 (with)"])
            if not chart_acts.empty:
                score_chart_col, dur_chart_col = st.columns(2)
                with score_chart_col:
                    score_cmp = chart_acts[["Activity", "Sleep score /100 (with)", "Sleep score /100 (baseline)"]].dropna()
                    if not score_cmp.empty:
                        st.caption("Avg sleep score — with vs baseline")
                        st.bar_chart(
                            score_cmp.set_index("Activity"),
                            use_container_width=True,
                            height=260,
                        )
                with dur_chart_col:
                    dur_cmp = act_df[["Activity", "Total sleep (h) (with)", "Total sleep (h) (baseline)"]].dropna()
                    if not dur_cmp.empty:
                        st.caption("Avg total sleep (h) — with vs baseline")
                        st.bar_chart(
                            dur_cmp.set_index("Activity"),
                            use_container_width=True,
                            height=260,
                        )

            # ── Deep / REM detail for activities with enough data ───────
            deep_rem_acts = act_df.dropna(subset=["Deep sleep (h) (with)", "REM sleep (h) (with)"])
            if not deep_rem_acts.empty:
                st.caption("Avg deep and REM sleep (h) when activity was logged")
                detail_df = deep_rem_acts[["Activity", "Deep sleep (h) (with)", "REM sleep (h) (with)"]].set_index("Activity")
                st.bar_chart(detail_df, use_container_width=True, height=240)

            # ── Night-by-night timeline for a selected activity ─────────
            if len(all_sleep_acts) > 0:
                st.markdown("**Selected activity trend (night by night)**")
                st.caption(
                    "This compares nights where the selected activity appears versus nights it does not, "
                    "so you can see whether it tends to align with better or worse sleep outcomes."
                )
                selected_act = st.selectbox(
                    "Select activity",
                    options=all_sleep_acts,
                    key="sleep_act_timeline_select",
                )
                timeline_rows = []
                all_annotated_dates = sorted(annotated_nights.keys())
                # Also include all sleep days in range for context
                all_sleep_dates = sorted(sleep_rows_ext.keys())
                context_dates = sorted(
                    set(all_sleep_dates)
                    | set(all_annotated_dates)
                )
                for d in context_dates:
                    s = sleep_rows_ext.get(d)
                    if not s:
                        continue
                    had_act = selected_act in night_activities.get(d, set())
                    score_value = s.get("sleep_score")
                    total_sleep_h = round(s["total_sleep_minutes"] / 60, 2) if s.get("total_sleep_minutes") else None
                    timeline_rows.append({
                        "Date": pd.to_datetime(d),
                        "Sleep score (with activity)": score_value if had_act else None,
                        "Sleep score (other nights)": score_value if not had_act else None,
                        "Total sleep (h) with activity": total_sleep_h if had_act else None,
                        "Total sleep (h) other nights": total_sleep_h if not had_act else None,
                        "Deep sleep (h)": round(s["deep_sleep_minutes"] / 60, 2) if s.get("deep_sleep_minutes") else None,
                    })
                if timeline_rows:
                    tl_df = pd.DataFrame(timeline_rows).set_index("Date")

                    with_nights = int(tl_df["Sleep score (with activity)"].notna().sum())
                    other_nights = int(tl_df["Sleep score (other nights)"].notna().sum())
                    stats_col1, stats_col2 = st.columns(2)
                    with stats_col1:
                        st.metric("Nights with selected activity", with_nights)
                    with stats_col2:
                        st.metric("Other nights", other_nights)

                    tl_col1, tl_col2 = st.columns(2)
                    with tl_col1:
                        score_tl = tl_df[["Sleep score (with activity)", "Sleep score (other nights)"]]
                        if not score_tl.empty:
                            st.caption("Sleep score over time: selected activity nights vs other nights")
                            st.line_chart(score_tl, use_container_width=True, height=220)
                    with tl_col2:
                        deep_tl = tl_df[["Total sleep (h) with activity", "Total sleep (h) other nights", "Deep sleep (h)"]]
                        if not deep_tl.empty:
                            st.caption("Sleep duration/deep sleep over time")
                            st.line_chart(deep_tl, use_container_width=True, height=220)
        else:
            st.info("Not enough annotated nights with Garmin data to compare yet.")
    else:
        st.info("No annotated nights with Garmin sleep data found for this date range.")
elif sleep_cat_ids and not annotated_nights:
    section_header(
        "Before/During Sleep Activities & Sleep Quality",
        "Links sleep-related activity categories to Garmin sleep outcomes once enough overlap exists.",
    )
    st.info(
        "No nights found with Before Sleep / During Sleep activities logged alongside Garmin sleep data yet. "
        "Log activities in those categories on evenings and this section will populate once sleep data syncs."
    )
