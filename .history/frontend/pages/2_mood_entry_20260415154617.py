import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components

API_BASE = "http://backend:8000"

st.set_page_config(page_title="Mood Entry", layout="centered")

# -----------------------------
# Load categories + activities
# -----------------------------
def load_categories():
    try:
        r = requests.get(f"{API_BASE}/categories/")
        return r.json()
    except:
        return []

def load_activities():
    try:
        r = requests.get(f"{API_BASE}/activities/")
        return r.json()
    except:
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
# Custom HTML chip CSS
# -----------------------------
st.markdown("""
<style>
.chip-container {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
}
.chip {
    padding: 6px 12px;
    border-radius: 16px;
    background-color: #f0f0f0;
    border: 1px solid #ccc;
    cursor: pointer;
    font-size: 14px;
    user-select: none;
}
.chip.selected {
    background-color: #4CAF50;
    color: white;
    border-color: #4CAF50;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Chip selection state
# -----------------------------
if "selected_activities" not in st.session_state:
    st.session_state.selected_activities = set()

# -----------------------------
# UK Date + Time Pickers
# -----------------------------
uk_tz = ZoneInfo("Europe/London")

entry_date = st.date_input(
    "Entry Date",
    datetime.datetime.now(uk_tz).date()
)

entry_time = st.time_input(
    "Entry Time",
    datetime.datetime.now(uk_tz).time()
)

entry_dt = datetime.datetime.combine(entry_date, entry_time, tzinfo=uk_tz)
timestamp_iso = entry_dt.isoformat()

# -----------------------------
# Mood Score + Notes
# -----------------------------
mood_score = st.slider("Mood Score", 1, 10, 5)
notes = st.text_area("Notes", "")

# -----------------------------
# Render categories + chips
# -----------------------------
st.markdown("### Activities")

# Hidden input to receive chip clicks
clicked = st.text_input("chip-input", key="chip-input", label_visibility="collapsed")

# Update session state when a chip is clicked
if clicked:
    aid = int(clicked)
    if aid in st.session_state.selected_activities:
        st.session_state.selected_activities.remove(aid)
    else:
        st.session_state.selected_activities.add(aid)
    st.session_state["chip-input"] = ""  # reset

for cat in categories:
    st.markdown(f"#### {cat['name']}")
    cid = cat["id"]
    cat_acts = activities_by_cat.get(cid, [])

    chip_html = """
    <script>
    function toggleChip(aid) {
        const input = window.parent.document.querySelector('input[id="chip-input"]');
        input.value = aid;
        input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    </script>
    <div class="chip-container">
    """

    for a in cat_acts:
        selected_class = "selected" if a["id"] in st.session_state.selected_activities else ""
        chip_html += f"""
        <div class="chip {selected_class}" onclick="toggleChip({a['id']})">
            {a['name']}
        </div>
        """

    chip_html += "</div>"

    components.html(chip_html, height=200)

# -----------------------------
# Submit Button
# -----------------------------
if st.button("Save Entry"):
    payload = {
        "mood": mood_score,
        "notes": notes,
        "timestamp": timestamp_iso,
        "activity_ids": list(st.session_state.selected_activities)
    }

    r = requests.post(f"{API_BASE}/mood/", json=payload)

    if r.status_code == 200:
        st.success("Mood entry saved!")
        st.session_state.selected_activities = set()
    else:
        st.error(f"Error: {r.text}")
