import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo

API_BASE = "http://backend:8000"

st.set_page_config(page_title="Mood Entry", layout="centered")

# Reset handling
if st.session_state.get("reset_form", False):
    for k in ["entry_date", "entry_time", "mood_score", "notes"]:
        st.session_state.pop(k, None)
    st.session_state["selected_activities"] = set()
    for key in list(st.session_state.keys()):
        if key.startswith("act_"):
            st.session_state.pop(key, None)
    st.session_state["reset_form"] = False

# Load categories + activities
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

activities_by_cat = {}
for a in activities:
    cid = a.get("category_id")
    activities_by_cat.setdefault(cid, []).append(a)

# CSS for compact chips
st.markdown(
    """
<style>
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.chip-checkbox { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 14px; background-color: #f0f0f0; border: 1px solid #ccc; cursor: pointer; font-size: 13px; }
.chip-checkbox input[type="checkbox"] { display: none; }
.chip-checkbox.checked { background-color: #4CAF50 !important; color: white !important; border-color: #4CAF50 !important; }
.category-title { margin-top: 10px; margin-bottom: 4px; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)

# Session defaults
if "selected_activities" not in st.session_state:
    st.session_state.selected_activities = set()

uk_tz = ZoneInfo("Europe/London")
now_uk = datetime.datetime.now(uk_tz)

st.session_state.setdefault("entry_date", now_uk.date())
st.session_state.setdefault("entry_time", now_uk.time())
st.session_state.setdefault("mood_score", 3)
st.session_state.setdefault("notes", "")

# Date/time
entry_date = st.date_input("Entry Date", value=st.session_state.entry_date, key="entry_date")
entry_time = st.time_input("Entry Time", value=st.session_state.entry_time, key="entry_time")

entry_dt = datetime.datetime.combine(st.session_state.entry_date, st.session_state.entry_time, tzinfo=uk_tz)
timestamp_iso = entry_dt.isoformat()

# Mood score (1–5)
mood_score = st.slider("Mood Score (1 = Great, 5 = Rubbish)", 1, 5, st.session_state.mood_score, key="mood_score")

# Notes
notes = st.text_area("Notes", st.session_state.notes, key="notes")

# Activities
st.markdown("### Activities")

def render_chip_row(items, cols=4):
    col_objs = st.columns(cols)
    for idx, item in enumerate(items):
        col = col_objs[idx % cols]
        with col:
            aid = item["id"]
            key = f"act_{aid}"
            checked = st.checkbox(item["name"], value=(aid in st.session_state.selected_activities), key=key)
            if checked:
                st.session_state.selected_activities.add(aid)
            else:
                st.session_state.selected_activities.discard(aid)

for cat in categories:
    st.markdown(f"<div class='category-title'>{cat.get('name','Category')}</div>", unsafe_allow_html=True)
    render_chip_row(activities_by_cat.get(cat["id"], []), cols=4)

# Save
if st.button("Save Entry"):
    payload = {
        "mood_score": mood_score,
        "notes": notes,
        "timestamp": timestamp_iso,
        "activity_ids": sorted(list(st.session_state.selected_activities)),
    }

    try:
        r = requests.post(f"{API_BASE}/mood/", json=payload)
        if r.status_code in (200, 201):
            st.success("Mood entry saved!")
            st.session_state.reset_form = True
            st.session_state["_force_rerun_counter"] = st.session_state.get("_force_rerun_counter", 0) + 1
        else:
            st.error(f"Error: {r.status_code} {r.text}")
    except Exception as exc:
        st.error(f"Error saving entry: {exc}")
