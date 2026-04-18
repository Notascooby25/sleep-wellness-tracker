import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo

API_BASE = "http://backend:8000"

st.set_page_config(page_title="Mood Entry", layout="wide")


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
    try:
        r = requests.get(f"{API_BASE}/categories/", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def load_activities():
    try:
        r = requests.get(f"{API_BASE}/activities/", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


categories = load_categories()
activities = load_activities()

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

uk_tz = ZoneInfo("Europe/London")
now_uk = datetime.datetime.now(uk_tz)

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

mood_score = st.slider("Mood Score (1 = Great, 5 = Rubbish)", 1, 5, st.session_state.mood_score, key="mood_score")

active_mood_colour = MOOD_COLOURS.get(mood_score, "#facc15")
st.markdown(
    f"""
<style>
div[data-testid="stSlider"] div[data-baseweb="slider"] > div > div:nth-child(2) {{
    background: {active_mood_colour} !important;
}}

div[data-testid="stSlider"] div[data-baseweb="slider"] [role="slider"] {{
    background: {active_mood_colour} !important;
    border-color: {active_mood_colour} !important;
    box-shadow: 0 0 0 1px {active_mood_colour} !important;
}}

.mood-colour-line {{
    height: 5px;
    border-radius: 999px;
    margin-top: -0.25rem;
    margin-bottom: 0.9rem;
    background: {active_mood_colour};
}}
</style>
<div class="mood-colour-line"></div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">Activities</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="activity-topbar"><span class="activity-count">{len(st.session_state.selected_activities)} selected</span></div>',
    unsafe_allow_html=True,
)

count_col, clear_col = st.columns([0.78, 0.22])
with count_col:
    st.caption("Tip: tap chips to toggle, then switch categories using tabs.")
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
else:
    st.warning("No activity categories found.")

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
