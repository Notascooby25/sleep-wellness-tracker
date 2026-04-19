import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo

API_BASE = "http://backend:8000"

st.set_page_config(page_title="Mood Entry", layout="wide")


def fmt_minutes(total_minutes):
    if total_minutes is None:
        return "-"
    mins = max(0, int(total_minutes))
    return f"{mins // 60}h {mins % 60:02d}m"


def reset_entry_form_state():
    for k in ["entry_date", "entry_time", "mood_score", "notes"]:
        st.session_state.pop(k, None)
    st.session_state["selected_activities"] = set()
    for key in list(st.session_state.keys()):
        if key.startswith("act_") or key.startswith("pill_cat_"):
            st.session_state.pop(key, None)


if st.session_state.get("reset_form", False):
    reset_entry_form_state()
    st.session_state["reset_form"] = False


@st.cache_data(ttl=300, show_spinner=False)
def load_categories():
    endpoints = [f"{API_BASE}/categories/", f"{API_BASE}/categories"]
    last_exc = None
    for endpoint in endpoints:
        try:
            r = requests.get(endpoint, timeout=3)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
        except Exception as exc:
            last_exc = exc

    if last_exc:
        st.session_state["mood_entry_last_load_error"] = str(last_exc)
    try:
        return []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def load_activities():
    endpoints = [f"{API_BASE}/activities/", f"{API_BASE}/activities"]
    last_exc = None
    for endpoint in endpoints:
        try:
            r = requests.get(endpoint, timeout=3)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
        except Exception as exc:
            last_exc = exc

    if last_exc:
        st.session_state["mood_entry_last_load_error"] = str(last_exc)
    try:
        return []
    except Exception:
        return []


@st.cache_data(ttl=900, show_spinner=False)
def load_garmin_latest_sleep():
    try:
        r = requests.get(f"{API_BASE}/garmin/sleep/latest", timeout=4)
        r.raise_for_status()
        return r.json().get("data")
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def load_garmin_latest_battery():
    try:
        r = requests.get(f"{API_BASE}/garmin/body-battery/latest", timeout=4)
        r.raise_for_status()
        return r.json().get("data")
    except Exception:
        return None


categories = load_categories()
activities = load_activities()

if "mood_entry_last_load_error" not in st.session_state:
    st.session_state["mood_entry_last_load_error"] = ""

activities_by_cat = {}
for a in activities:
    cid = a.get("category_id")
    activities_by_cat.setdefault(cid, []).append(a)

st.markdown(
    """
<style>
:root {
    --bg-soft: #f4f7fb;
    --card-bg: #ffffff;
    --card-border: #d9e2ef;
    --text-main: #132238;
    --text-sub: #5f6f84;
    --chip-bg: #ecf2fb;
    --chip-border: #ccddf4;
    --chip-text: #1f4066;
    --chip-active-bg: #3c79c5;
    --chip-active-border: #3168ad;
    --chip-active-text: #f7fbff;
}

[data-testid="stAppViewContainer"] {
    background:
      radial-gradient(900px 260px at 8% -12%, #dbeafe 0%, transparent 45%),
      radial-gradient(900px 280px at 92% -18%, #e5f4ff 0%, transparent 42%),
      linear-gradient(180deg, #f9fbff 0%, #f2f6fc 100%);
}

.block-container {
    max-width: 1120px;
    padding-top: 1.2rem;
    padding-bottom: 1.5rem;
}

.hero {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
    margin-bottom: 12px;
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

.section-title {
    color: var(--text-main);
    font-size: 1.08rem;
    font-weight: 700;
    margin: 0.2rem 0 0.35rem;
}

.activity-topbar {
    background: #f8fbff;
    border: 1px solid #d7e6f7;
    border-radius: 12px;
    padding: 0.55rem 0.7rem;
    margin-bottom: 0.5rem;
}

.activity-count {
    color: #2a4e76;
    font-size: 0.86rem;
    font-weight: 650;
}

div[data-testid="stTabs"] {
    margin-top: 0.2rem;
}

button[data-baseweb="tab"] {
    border-radius: 999px;
    border: 1px solid #d6e5f7;
    background: #f3f8ff;
    color: #2d4f76;
    font-weight: 600;
    min-height: 32px;
    padding: 0 0.8rem;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: #d9eafe;
    border-color: #bfd9fa;
}

div[data-testid="stCheckbox"] {
    margin-bottom: 0.32rem;
}

div[data-testid="stCheckbox"] label {
    border-radius: 999px;
    border: 1px solid var(--chip-border);
    background: var(--chip-bg);
    padding: 0.26rem 0.66rem;
    width: 100%;
    min-height: 2.15rem;
    display: flex;
    align-items: center;
    transition: all 120ms ease-out;
}

div[data-testid="stCheckbox"] label p {
    margin: 0;
    color: var(--chip-text);
    font-size: 0.83rem;
    font-weight: 650;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    word-break: normal;
    overflow-wrap: normal;
}

div[data-testid="stCheckbox"] label input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
}

div[data-testid="stCheckbox"] label:has(input:checked) {
    background: var(--chip-active-bg);
    border-color: var(--chip-active-border);
}

div[data-testid="stCheckbox"] label:has(input:checked) p {
    color: var(--chip-active-text);
}

div[data-testid="stCheckbox"] svg {
    display: none;
}

[data-baseweb="tab-panel"] div[data-testid="stCheckbox"] {
    display: inline-block;
    vertical-align: top;
    width: 32.3%;
    margin-right: 1%;
}

[data-baseweb="tab-panel"] div[data-testid="stCheckbox"]:nth-child(3n) {
    margin-right: 0;
}

@media (max-width: 860px) {
    .block-container {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        padding-top: 0.95rem;
    }

    .hero h1 {
        font-size: 1.5rem;
    }

    .activity-count {
        font-size: 0.8rem;
    }

    [data-baseweb="tab-panel"] div[data-testid="stCheckbox"] {
        width: 48.9%;
        margin-right: 1.8%;
        margin-bottom: 0.4rem;
    }

    [data-baseweb="tab-panel"] div[data-testid="stCheckbox"]:nth-child(2n) {
        margin-right: 0;
    }

    div[data-testid="stCheckbox"] label p {
        font-size: 0.78rem;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

if "garmin_flash" not in st.session_state:
    st.session_state["garmin_flash"] = None

if st.session_state["garmin_flash"]:
    st.info(st.session_state["garmin_flash"])
    st.session_state["garmin_flash"] = None

st.markdown(
    """
<div class="hero">
    <h1>Mood Entry</h1>
    <p>Fast log, tap activities as chips, and save. Times are UK local time (Europe/London).</p>
</div>
""",
    unsafe_allow_html=True,
)

if "selected_activities" not in st.session_state:
    st.session_state.selected_activities = set()

# Keep selected ids in sync with currently available activities.
available_activity_ids = {a.get("id") for a in activities if a.get("id") is not None}
st.session_state.selected_activities.intersection_update(available_activity_ids)

uk_tz = ZoneInfo("Europe/London")
now_uk = datetime.datetime.now(uk_tz)

garmin_col, garmin_sync_col = st.columns([0.82, 0.18])
with garmin_col:
    if now_uk.hour < 12:
        sleep_data = load_garmin_latest_sleep()
        battery_data = load_garmin_latest_battery()
        with st.container(border=True):
            st.markdown("**Last Night Garmin Sleep**")
            if sleep_data:
                st.caption(
                    f"Duration {fmt_minutes(sleep_data.get('total_sleep_minutes'))} | "
                    f"Deep {fmt_minutes(sleep_data.get('deep_sleep_minutes'))} | "
                    f"Light {fmt_minutes(sleep_data.get('light_sleep_minutes'))} | "
                    f"REM {fmt_minutes(sleep_data.get('rem_sleep_minutes'))}"
                )
                if sleep_data.get("sleep_score") is not None:
                    st.caption(f"Sleep score: {sleep_data.get('sleep_score')}/100")
            else:
                st.caption("No Garmin sleep data yet. First sync starts from 08:00 UK.")

            if battery_data and battery_data.get("end_of_day_value") is not None:
                st.caption(f"Yesterday end-of-day body battery: {battery_data.get('end_of_day_value')}")
    else:
        st.caption("Garmin sleep summary appears in the morning; use Mood Log for historical sleep details.")

with garmin_sync_col:
    st.markdown("<div style='height: 0.35rem;'></div>", unsafe_allow_html=True)
    if st.button("Sync Garmin", use_container_width=True):
        try:
            resp = requests.post(f"{API_BASE}/garmin/sync-now?mode=smart", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                sleep_state = (data.get("sleep") or {}).get("status", "unknown")
                body_state = (data.get("body_battery") or {}).get("status", "unknown")
                load_garmin_latest_sleep.clear()
                load_garmin_latest_battery.clear()
                st.session_state["garmin_flash"] = f"Garmin sync result: sleep={sleep_state}, body={body_state}."
                st.rerun()
            else:
                st.error(f"Garmin sync failed: {resp.status_code} {resp.text}")
        except Exception as exc:
            st.error(f"Garmin sync failed: {exc}")

st.session_state.setdefault("entry_date", now_uk.date())
st.session_state.setdefault("entry_time", now_uk.time())
st.session_state.setdefault("mood_score", 3)
st.session_state.setdefault("notes", "")

MOOD_COLOURS = {
    1: "#2ecc71",  # great
    2: "#84cc16",  # good
    3: "#facc15",  # neutral
    4: "#fb923c",  # low
    5: "#ef4444",  # rubbish
}

st.markdown('<div class="section-title">Entry Details</div>', unsafe_allow_html=True)
date_col, time_col = st.columns(2)
with date_col:
    st.date_input("Entry Date", value=st.session_state.entry_date, key="entry_date")
with time_col:
    st.time_input("Entry Time", value=st.session_state.entry_time, key="entry_time")

entry_dt = datetime.datetime.combine(st.session_state.entry_date, st.session_state.entry_time, tzinfo=uk_tz)
timestamp_iso = entry_dt.isoformat()

st.markdown(
    """
<style>
/* Radio group: basic compact pills */
div[data-testid="stRadio"] [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    justify-content: stretch !important;
    gap: 0.3rem !important;
    width: 100% !important;
    margin-bottom: 0.9rem !important;
}

/* Override Streamlit generated fit-content wrappers so pills can span evenly */
.st-emotion-cache-zh2fnc {
    width: 100% !important;
}

div[data-testid="stRadio"] [role="radiogroup"] > * {
    width: 100% !important;
}

/* Hide any non-option label that Streamlit may inject for the field title */
div[data-testid="stRadio"] [role="radiogroup"] label:not(:has(input[type="radio"])) {
    display: none !important;
}

div[data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]) {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: center !important;
    flex: 1 1 0 !important;
    min-width: 0 !important;
    width: auto !important;
    min-height: 2.25rem !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    font-size: clamp(0.86rem, 3vw, 1rem) !important;
    color: #ffffff !important;
    cursor: pointer !important;
    background: #2ecc71 !important;
    border: 1px solid #28b864 !important;
    transition: all 120ms ease !important;
    padding: 0.24rem 0.62rem !important;
    gap: 0 !important;
    box-sizing: border-box !important;
}

/* Hide the native radio dot */
div[data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]) > div:first-child {
    display: none !important;
}

div[data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]) > div:last-child {
    color: #ffffff !important;
    font-size: clamp(0.86rem, 3vw, 1rem) !important;
    font-weight: 700 !important;
    line-height: 1.1 !important;
    text-align: center !important;
    white-space: nowrap !important;
}

/* Per-score colours */
div[data-testid="stRadio"] [role="radiogroup"] label:has(input[value="2"]) {
    background: #84cc16 !important;
    border-color: #74b412 !important;
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input[value="3"]) {
    background: #facc15 !important;
    border-color: #eab308 !important;
    color: #213247 !important;
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input[value="3"]) > div:last-child {
    color: #213247 !important;
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input[value="4"]) {
    background: #fb923c !important;
    border-color: #ea7b21 !important;
}
div[data-testid="stRadio"] [role="radiogroup"] label:has(input[value="5"]) {
    background: #ef4444 !important;
    border-color: #dc2626 !important;
}

/* Selected state */
div[data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]:checked) {
    box-shadow: 0 0 0 2px rgba(19,34,56,0.22) !important;
    transform: translateY(-1px) !important;
}

div[data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]:checked) > div:last-child {
    font-weight: 800 !important;
}

@media (max-width: 520px) {
    div[data-testid="stRadio"] [role="radiogroup"] {
        gap: 0.24rem !important;
    }

    div[data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]) {
        min-height: 2.05rem !important;
        padding: 0.16rem 0.36rem !important;
        font-size: 0.8rem !important;
    }

    div[data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]) > div:last-child {
        font-size: 0.8rem !important;
    }
}

/* Style the info popover button */
div[data-testid="stPopover"] button {
    padding: 0 0.55rem !important;
    min-height: 1.6rem !important;
    font-size: 0.82rem !important;
    border-radius: 999px !important;
    border: 1px solid #ccd9ee !important;
    background: #f0f5fd !important;
    color: #3168ad !important;
    line-height: 1.1 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# Mood score title with info popover
mood_title_col, mood_info_col = st.columns([0.88, 0.12])
with mood_title_col:
    st.markdown('<div class="section-title">Mood Score</div>', unsafe_allow_html=True)
with mood_info_col:
    with st.popover("Info"):
        st.markdown(
            """
**Mood scoring guide**

| Score | Meaning |
|-------|---------|
| 🟢 **1** | Great — feeling really good |
| 🟡 **2** | Good — above average |
| 🟡 **3** | Neutral — neither good nor bad |
| 🟠 **4** | Low — below average |
| 🔴 **5** | Rubbish — really struggling |
"""
        )

mood_score = st.radio(
    "Mood Score",
    options=[1, 2, 3, 4, 5],
    format_func=lambda x: f"{x}",
    horizontal=True,
    key="mood_score",
    label_visibility="collapsed",
)

st.markdown('<div class="section-title">Activities</div>', unsafe_allow_html=True)
count_col, clear_col = st.columns([0.78, 0.22])
with count_col:
    st.caption("Tap chips to toggle, then switch categories using tabs.")
with clear_col:
    if st.button("Clear", use_container_width=True):
        reset_entry_form_state()
        st.rerun()

if categories:
    tabs = st.tabs([cat.get("name", "Category") for cat in categories])
    for cat, tab in zip(categories, tabs):
        with tab:
            items = activities_by_cat.get(cat.get("id"), [])
            if not items:
                st.caption("No activities in this category.")
                continue

            option_ids = [item["id"] for item in items]
            name_lookup = {item["id"]: item["name"] for item in items}
            default_selected = [aid for aid in option_ids if aid in st.session_state.selected_activities]

            key = f"pill_cat_{cat.get('id')}"
            if hasattr(st, "pills"):
                chosen_ids = st.pills(
                    "Activities",
                    options=option_ids,
                    default=default_selected,
                    selection_mode="multi",
                    format_func=lambda aid: name_lookup.get(aid, str(aid)),
                    key=key,
                    label_visibility="collapsed",
                )
                chosen_ids = chosen_ids or []
            else:
                chosen_ids = st.multiselect(
                    "Activities",
                    options=option_ids,
                    default=default_selected,
                    format_func=lambda aid: name_lookup.get(aid, str(aid)),
                    key=key,
                    label_visibility="collapsed",
                )

            cat_option_set = set(option_ids)
            st.session_state.selected_activities.difference_update(cat_option_set)
            st.session_state.selected_activities.update(set(chosen_ids))
elif activities:
    st.info("No categories found, showing all activities in a single group.")
    option_ids = [item["id"] for item in activities if item.get("id") is not None]
    name_lookup = {item["id"]: item["name"] for item in activities if item.get("id") is not None}
    default_selected = [aid for aid in option_ids if aid in st.session_state.selected_activities]

    if hasattr(st, "pills"):
        chosen_ids = st.pills(
            "Activities",
            options=option_ids,
            default=default_selected,
            selection_mode="multi",
            format_func=lambda aid: name_lookup.get(aid, str(aid)),
            key="pill_uncategorized_all",
            label_visibility="collapsed",
        )
        chosen_ids = chosen_ids or []
    else:
        chosen_ids = st.multiselect(
            "Activities",
            options=option_ids,
            default=default_selected,
            format_func=lambda aid: name_lookup.get(aid, str(aid)),
            key="pill_uncategorized_all",
            label_visibility="collapsed",
        )

    st.session_state.selected_activities = set(chosen_ids)
else:
    st.warning("No categories or activities found. Recreate them from the management pages.")
    if hasattr(st, "page_link"):
        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            st.page_link("pages/4_manage_categories.py", label="Open Manage Categories")
        with nav_col2:
            st.page_link("pages/5_manage_activities.py", label="Open Manage Activities")
    else:
        st.caption("Use the left sidebar to open Manage Categories and Manage Activities.")
    if st.session_state.get("mood_entry_last_load_error"):
        st.caption(f"Last load error: {st.session_state['mood_entry_last_load_error']}")

st.markdown('<div class="section-title">Notes</div>', unsafe_allow_html=True)
notes = st.text_area("Notes", st.session_state.notes, key="notes", height=120, label_visibility="collapsed")

if st.button("Save Entry", type="primary", use_container_width=True):
    payload = {
        "mood_score": mood_score,
        "notes": notes,
        "timestamp": timestamp_iso,
        "activity_ids": sorted(list(st.session_state.selected_activities)),
    }

    try:
        r = requests.post(f"{API_BASE}/mood/", json=payload, timeout=4)
        if r.status_code in (200, 201):
            st.success("Mood entry saved")
            st.session_state["reset_form"] = True
            st.rerun()
        else:
            st.error(f"Error: {r.status_code} {r.text}")
    except Exception as exc:
        st.error(f"Error saving entry: {exc}")
