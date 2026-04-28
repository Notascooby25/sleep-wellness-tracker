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


# ── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_mood_all():
    try:
        r = requests.get(f"{API_BASE}/mood/", timeout=10)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


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


mood_entries_all = load_mood_all()
sleep_rows = load_garmin_range("sleep", start_iso, end_iso)
body_rows = load_garmin_range("body-battery", start_iso, end_iso)
hrv_rows = load_garmin_range("hrv", start_iso, end_iso)
rhr_rows = load_garmin_range("resting-heart-rate", start_iso, end_iso)
activities_list = load_activities_list()
activity_name_map = {a["id"]: a["name"] for a in activities_list if a.get("id")}

# Filter mood entries to the selected date range
def entry_date_uk(entry) -> datetime.date | None:
    try:
        ts = entry.get("timestamp", "")
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(ts).astimezone(UK_TZ).date()
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
        ts = entry.get("timestamp", "")
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt_uk = datetime.datetime.fromisoformat(ts).astimezone(UK_TZ)
        day_str = dt_uk.date().isoformat()
    except Exception:
        continue
    daily_mood.setdefault(day_str, []).append(score)

daily_avg_mood = {d: sum(v) / len(v) for d, v in daily_mood.items()}

# ── Summary KPI cards ─────────────────────────────────────────────────────────
st.markdown("<div class='section-heading'>Summary</div>", unsafe_allow_html=True)

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
    st.markdown("<div class='section-heading'>Mood Trend</div>", unsafe_allow_html=True)
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
    st.markdown("<div class='section-heading'>Sleep vs Mood</div>", unsafe_allow_html=True)
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
if hrv_rows or body_rows:
    st.markdown("<div class='section-heading'>Recovery Metrics</div>", unsafe_allow_html=True)
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
if rated_scores:
    st.markdown("<div class='section-heading'>Mood Distribution</div>", unsafe_allow_html=True)
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
                ts = entry.get("timestamp", "")
                if ts.endswith("Z"):
                    ts = ts[:-1] + "+00:00"
                dt_uk = datetime.datetime.fromisoformat(ts).astimezone(UK_TZ)
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
if mood_entries and activity_name_map:
    st.markdown("<div class='section-heading'>Activity Log</div>", unsafe_allow_html=True)

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
