import datetime
import os
from zoneinfo import ZoneInfo

import requests
import streamlit as st


API_BASE = os.getenv("API_BASE", "http://backend:8000")
UK_TZ = ZoneInfo("Europe/London")
DEFAULT_RANGE_DAYS = 30


st.set_page_config(page_title="Garmin Log", layout="wide")

st.markdown(
    """
<style>
:root {
    --bg-soft: #f4f7fb;
    --card-bg: #ffffff;
    --card-border: #d9e2ef;
    --text-main: #132238;
    --text-sub: #5f6f84;
    --pill-bg: #eef4fb;
    --pill-border: #d3e1f3;
    --pill-text: #264a72;
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

.hero h1 {
    margin: 0;
    color: var(--text-main);
    font-size: 1.8rem;
    line-height: 1.15;
}

.hero p {
    margin: 8px 0 0;
    color: var(--text-sub);
    font-size: 0.96rem;
}

.summary-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 0.8rem 0.9rem;
    box-shadow: 0 6px 14px rgba(30, 58, 138, 0.05);
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 0.75rem;
    margin: 0.25rem 0 0.9rem;
}

.summary-label {
    color: var(--text-sub);
    font-size: 0.76rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.summary-value {
    color: var(--text-main);
    font-size: 1.25rem;
    font-weight: 800;
    margin-top: 0.18rem;
}

.day-title {
    color: var(--text-main);
    font-size: 1.02rem;
    font-weight: 800;
}

.metric-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    color: var(--pill-text);
    background: var(--pill-bg);
    border: 1px solid var(--pill-border);
    border-radius: 999px;
    padding: 0.16rem 0.56rem;
    font-size: 0.74rem;
    font-weight: 700;
    margin-right: 0.34rem;
    margin-bottom: 0.34rem;
}

.metric-name {
    color: var(--text-sub);
    font-size: 0.78rem;
    font-weight: 700;
    margin-bottom: 0.18rem;
}

.metric-value {
    color: var(--text-main);
    font-size: 0.96rem;
    font-weight: 700;
}

.metric-empty {
    color: #8091a7;
    font-size: 0.86rem;
}

@media (max-width: 860px) {
    .block-container {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        padding-top: 0.95rem;
    }

    .hero h1 {
        font-size: 1.52rem;
    }

    .summary-value {
        font-size: 1.02rem;
    }

    .summary-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.55rem;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


def fmt_minutes(value):
    if value is None:
        return "No data"
    total = int(value)
    return f"{total // 60}h {total % 60:02d}m"


def fmt_ml(value):
    if value is None:
        return "No data"
    return f"{int(value)} ml"


def metric_count(rows_by_date: dict) -> int:
    return sum(1 for row in rows_by_date.values() if isinstance(row, dict))


@st.cache_data(ttl=900, show_spinner=False)
def load_metric_range(metric_path: str, start_date: str, end_date: str):
    try:
        response = requests.get(
            f"{API_BASE}/garmin/{metric_path}/range",
            params={"start_date": start_date, "end_date": end_date},
            timeout=8,
        )
        response.raise_for_status()
        rows = response.json().get("data") or []
        return {
            row.get("date"): row
            for row in rows
            if isinstance(row, dict) and row.get("date")
        }
    except Exception:
        return {}


def clear_garmin_cache():
    load_metric_range.clear()


st.session_state.setdefault("garmin_log_flash", None)

if st.session_state["garmin_log_flash"]:
    st.info(st.session_state["garmin_log_flash"])
    st.session_state["garmin_log_flash"] = None


today = datetime.datetime.now(UK_TZ).date()
default_start = today - datetime.timedelta(days=DEFAULT_RANGE_DAYS - 1)

st.markdown(
    """
<div class="hero">
    <h1>Garmin Log</h1>
    <p>Daily Garmin recovery and wellness summaries. Sleep and body battery stay visible on the mood pages; this page is for the wider Garmin view.</p>
</div>
""",
    unsafe_allow_html=True,
)

control_cols = st.columns([0.3, 0.3, 0.2, 0.2])
with control_cols[0]:
    start_date = st.date_input("Start date", value=default_start, max_value=today)
with control_cols[1]:
    end_date = st.date_input("End date", value=today, min_value=start_date, max_value=today)
with control_cols[2]:
    if st.button("Refresh", use_container_width=True):
        clear_garmin_cache()
        st.rerun()
with control_cols[3]:
    sync_now_clicked = st.button("Sync Garmin", use_container_width=True, type="primary")

with st.expander("Sync settings", expanded=False):
    settings_cols = st.columns([0.45, 0.2, 0.18, 0.17])
    with settings_cols[0]:
        sync_scope = st.selectbox(
            "Sync scope",
            options=[
                ("smart", "Smart (windowed)"),
                ("all", "All metrics"),
                ("sleep", "Sleep only"),
                ("body", "Body Battery only"),
                ("hrv", "HRV only"),
                ("rhr", "Resting HR only"),
                ("stress", "Stress only"),
                ("hydration", "Hydration only"),
            ],
            format_func=lambda item: item[1],
            index=0,
            help="Single-metric sync is usually more reliable for larger backfills.",
        )
    with settings_cols[1]:
        sync_days = st.number_input(
            "Backfill days",
            min_value=1,
            max_value=365,
            value=30,
            step=1,
            help="Overrides env backfill days for this sync request only.",
        )
    with settings_cols[2]:
        force_sync = st.checkbox("Force sync", value=False)
    with settings_cols[3]:
        show_empty_days = st.checkbox("Show empty days", value=False)

if sync_now_clicked:
    try:
        selected_mode = sync_scope[0]
        params = {
            "mode": selected_mode,
            "force": "true" if force_sync else "false",
            "backfill_days": int(sync_days),
        }
        response = requests.post(f"{API_BASE}/garmin/sync-now", params=params, timeout=240)
        if response.status_code == 200:
            data = response.json()
            clear_garmin_cache()
            status_parts = []
            for key, value in data.items():
                if isinstance(value, dict):
                    status = value.get("status", "unknown")
                    reason = value.get("reason")
                    suffix = f" ({reason})" if reason else ""
                    status_parts.append(f"{key}={status}{suffix}")
                else:
                    status_parts.append(f"{key}=unknown")
            st.session_state["garmin_log_flash"] = "Garmin sync result: " + ", ".join(status_parts)
            st.rerun()
        elif response.status_code == 429:
            st.warning("Garmin is rate-limiting this IP. Wait a few minutes and try again.")
        else:
            st.error(f"Garmin sync failed: {response.status_code} {response.text}")
    except Exception as exc:
        st.error(f"Garmin sync failed: {exc}")

start_iso = start_date.isoformat()
end_iso = end_date.isoformat()

sleep_rows = load_metric_range("sleep", start_iso, end_iso)
body_rows = load_metric_range("body-battery", start_iso, end_iso)
hrv_rows = load_metric_range("hrv", start_iso, end_iso)
rhr_rows = load_metric_range("resting-heart-rate", start_iso, end_iso)
stress_rows = load_metric_range("stress", start_iso, end_iso)
hydration_rows = load_metric_range("hydration", start_iso, end_iso)

summary_data = [
    ("Sleep days", metric_count(sleep_rows)),
    ("Body battery days", metric_count(body_rows)),
    ("HRV days", metric_count(hrv_rows)),
    ("Resting HR days", metric_count(rhr_rows)),
    ("Stress days", metric_count(stress_rows)),
    ("Hydration days", metric_count(hydration_rows)),
]

summary_cards_html = "".join(
    f"<div class='summary-card'><div class='summary-label'>{label}</div><div class='summary-value'>{value}</div></div>"
    for label, value in summary_data
)
st.markdown(f"<div class='summary-grid'>{summary_cards_html}</div>", unsafe_allow_html=True)

all_dates = sorted(
    {
        *sleep_rows.keys(),
        *body_rows.keys(),
        *hrv_rows.keys(),
        *rhr_rows.keys(),
        *stress_rows.keys(),
        *hydration_rows.keys(),
    },
    reverse=True,
)

if not all_dates:
    st.markdown("<div class='summary-card' style='margin-top: 1rem;'>No Garmin data found for this date range yet.</div>", unsafe_allow_html=True)

for idx, date_str in enumerate(all_dates):
    sleep_row = sleep_rows.get(date_str)
    body_row = body_rows.get(date_str)
    hrv_row = hrv_rows.get(date_str)
    rhr_row = rhr_rows.get(date_str)
    stress_row = stress_rows.get(date_str)
    hydration_row = hydration_rows.get(date_str)

    if not show_empty_days and not any([sleep_row, body_row, hrv_row, rhr_row, stress_row, hydration_row]):
        continue

    day = datetime.date.fromisoformat(date_str)
    pill_parts = []
    if sleep_row and sleep_row.get("sleep_score") is not None:
        pill_parts.append(f"<span class='metric-pill'>Sleep score {sleep_row.get('sleep_score')}/100</span>")
    if body_row and body_row.get("end_of_day_value") is not None:
        pill_parts.append(f"<span class='metric-pill'>Body battery {body_row.get('end_of_day_value')}</span>")
    if hrv_row and hrv_row.get("weekly_avg") is not None:
        pill_parts.append(f"<span class='metric-pill'>HRV {hrv_row.get('weekly_avg')}</span>")
    if rhr_row and rhr_row.get("resting_heart_rate") is not None:
        pill_parts.append(f"<span class='metric-pill'>Resting HR {rhr_row.get('resting_heart_rate')}</span>")

    is_latest_day = idx == 0
    with st.expander(day.strftime("%A, %d %B %Y"), expanded=is_latest_day):
        if pill_parts:
            st.markdown("".join(pill_parts), unsafe_allow_html=True)

        left_col, right_col = st.columns(2)
        with left_col:
            with st.container(border=True):
                st.markdown("<div class='metric-name'>Sleep</div>", unsafe_allow_html=True)
                if sleep_row:
                    st.markdown(
                        f"<div class='metric-value'>{fmt_minutes(sleep_row.get('total_sleep_minutes'))}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"Deep {fmt_minutes(sleep_row.get('deep_sleep_minutes'))} | Light {fmt_minutes(sleep_row.get('light_sleep_minutes'))} | REM {fmt_minutes(sleep_row.get('rem_sleep_minutes'))}"
                    )
                else:
                    st.markdown("<div class='metric-empty'>No sleep data</div>", unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("<div class='metric-name'>HRV</div>", unsafe_allow_html=True)
                if hrv_row:
                    status = hrv_row.get("status") or "No status"
                    st.markdown(
                        f"<div class='metric-value'>{hrv_row.get('weekly_avg') or 'No data'}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Baseline {hrv_row.get('baseline_low') or 'n/a'} to {hrv_row.get('baseline_high') or 'n/a'} | {status}")
                else:
                    st.markdown("<div class='metric-empty'>No HRV data</div>", unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("<div class='metric-name'>Stress</div>", unsafe_allow_html=True)
                if stress_row:
                    st.markdown(
                        f"<div class='metric-value'>{stress_row.get('overall_stress_level') or 'No data'}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"Rest {stress_row.get('rest_stress_duration') or 'n/a'} | Low {stress_row.get('low_stress_duration') or 'n/a'} | Medium {stress_row.get('medium_stress_duration') or 'n/a'} | High {stress_row.get('high_stress_duration') or 'n/a'}"
                    )
                else:
                    st.markdown("<div class='metric-empty'>No stress data</div>", unsafe_allow_html=True)

        with right_col:
            with st.container(border=True):
                st.markdown("<div class='metric-name'>Body Battery</div>", unsafe_allow_html=True)
                if body_row:
                    st.markdown(
                        f"<div class='metric-value'>{body_row.get('end_of_day_value') or 'No data'}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"Morning {body_row.get('morning_value') or 'n/a'} | Peak {body_row.get('peak_value') or 'n/a'} | Low {body_row.get('low_value') or 'n/a'}"
                    )
                else:
                    st.markdown("<div class='metric-empty'>No body battery data</div>", unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("<div class='metric-name'>Resting Heart Rate</div>", unsafe_allow_html=True)
                if rhr_row:
                    st.markdown(
                        f"<div class='metric-value'>{rhr_row.get('resting_heart_rate') or 'No data'} bpm</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Min {rhr_row.get('min_heart_rate') or 'n/a'} | Max {rhr_row.get('max_heart_rate') or 'n/a'}")
                else:
                    st.markdown("<div class='metric-empty'>No resting heart rate data</div>", unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown("<div class='metric-name'>Hydration</div>", unsafe_allow_html=True)
                if hydration_row:
                    st.markdown(
                        f"<div class='metric-value'>{fmt_ml(hydration_row.get('consumed_ml'))}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Goal {fmt_ml(hydration_row.get('goal_ml'))}")
                else:
                    st.markdown("<div class='metric-empty'>No hydration data</div>", unsafe_allow_html=True)