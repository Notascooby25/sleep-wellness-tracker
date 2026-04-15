import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo

API_BASE = "http://backend:8000"

st.set_page_config(page_title="Mood Entry", layout="centered")

# -----------------------------
# Load categories + activities
# -----------------------------
def load_categories():
    try:
        r = requests.get(f"{API_BASE}/categories/")
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def load_activities():
    try:
        r = requests.get(f"{API_BASE}/activities/")
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

categories = load_categories()
activities = load_activities()

# Group activities by category_id
activities_by_cat = {}
for a in activities:
    cid = a["category_id"]
    if cid not in activities_by_cat:
        activities_by_cat[cid] = []
    activities_by_cat[cid].append(a)

# -----------------------------
# Custom CSS to make checkboxes look like chips
# -----------------------------
st.markdown("""
<style>
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
    align-items: center;
}
.chip-checkbox {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 16px;
    background-color: #f0f0f0;
    border: 1px solid #ccc;
    cursor: pointer;
    font-size: 14px;
    user-select: none;
}
.chip-checkbox input[type="checkbox"] {
    display: none;
}
.chip-checkbox.checked {
    background-color: #4CAF50 !important;
    color: white !important;
    border-color: #4CAF50 !important;
}
.category-title {
    margin-top: 12px;
    margin-bottom: 6px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Session state for selected activities and form persistence
# -----------------------------
if "selected_activities" not in st.session_state:
    st.session_state.selected_activities = set()

# Ensure persistent keys for date/time so user edits don't reset
uk_tz = ZoneInfo("Europe/London")
now_uk = datetime.datetime.now(uk_tz)

# Initialize session_state values only once
if "entry_date" not in st.session_state:
    st.session_state.entry_date = now_uk.date()
if "entry_time" not in st.session_state:
    # store as time object
    st.session_state.entry_time = now_uk.time()

# -----------------------------
# UK Date + Time Pickers (persist via key)
# -----------------------------
# Using key= ensures Streamlit stores the widget value in session_state and won't reset to "now" on rerun.
entry_date = st.date_input(
    "Entry Date",
    value=st.session_state.entry_date,
    key="entry_date"
)

entry_time = st.time_input(
    "Entry Time",
    value=st.session_state.entry_time,
    key="entry_time"
)

# Keep session_state in sync (Streamlit updates keys automatically, but ensure local vars reflect them)
st.session_state.entry_date = entry_date
st.session_state.entry_time = entry_time

# Combine into timezone-aware datetime
entry_dt = datetime.datetime.combine(st.session_state.entry_date, st.session_state.entry_time, tzinfo=uk_tz)
timestamp_iso = entry_dt.isoformat()

# -----------------------------
# Mood Score + Notes (persisted by keys if desired)
# -----------------------------
if "mood_score" not in st.session_state:
    st.session_state.mood_score = 5
mood_score = st.slider("Mood Score", 1, 10, st.session_state.mood_score, key="mood_score")
notes = st.text_area("Notes", "", key="notes")

# -----------------------------
# Render categories + activity chips (checkbox-based)
# -----------------------------
st.markdown("### Activities")

# Helper to render chips in rows using columns
def render_chip_row(items, cols=4):
    col_objs = st.columns(cols)
    for idx, item in enumerate(items):
        col = col_objs[idx % cols]
        with col:
            aid = item["id"]
            key = f"act_{aid}"
            default_checked = aid in st.session_state.selected_activities
            # Use checkbox with a stable key so Streamlit persists the checked state
            checked = st.checkbox(item["name"], value=default_checked, key=key)
            if checked and aid not in st.session_state.selected_activities:
                st.session_state.selected_activities.add(aid)
            if (not checked) and (aid in st.session_state.selected_activities):
                st.session_state.selected_activities.remove(aid)

for cat in categories:
    st.markdown(f"<div class='category-title'>{cat['name']}</div>", unsafe_allow_html=True)
    cid = cat["id"]
    cat_acts = activities_by_cat.get(cid, [])
    if not cat_acts:
        st.write("_No activities_")
        continue
    render_chip_row(cat_acts, cols=4)

# -----------------------------
# Submit Button
# -----------------------------
if st.button("Save Entry"):
    payload = {
        "mood_score": mood_score,
        "notes": notes,
        "timestamp": timestamp_iso,
        "activity_ids": sorted(list(st.session_state.selected_activities))
    }

    try:
        r = requests.post(f"{API_BASE}/mood/", json=payload)
        if r.status_code == 200:
            st.success("Mood entry saved!")
            # Reset selected activities and form fields
            st.session_state.selected_activities = set()
            # Clear checkbox keys so they re-render unchecked
            for a in activities:
                key = f"act_{a['id']}"
                if key in st.session_state:
                    del st.session_state[key]
            # Optionally reset mood and notes but keep date/time as the user's choice
            st.session_state.mood_score = 5
            st.session_state.notes = ""
            # Do not reset entry_date/entry_time so user can make multiple entries for same time/day
            st.experimental_rerun()
        else:
            st.error(f"Error: {r.text}")
    except Exception as exc:
        st.error(f"Error saving entry: {exc}")
