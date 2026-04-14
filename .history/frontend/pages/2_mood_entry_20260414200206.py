import os
import streamlit as st
import requests
import time
from datetime import datetime, timezone
from requests.exceptions import RequestException
from json import JSONDecodeError

API_BASE = os.getenv("API_BASE", "http://backend:8000")

# -----------------------------
# Helpers
# -----------------------------
def fetch_json(path, retries=5, delay=1.0, timeout=3):
    url = f"{API_BASE}{path}"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                try:
                    return r.json()
                except JSONDecodeError:
                    st.error("Backend returned invalid JSON.")
                    return []
            else:
                st.warning(f"Backend returned status {r.status_code} for {path}")
                return []
        except RequestException as e:
            if attempt == retries:
                st.error(f"Failed to reach backend after {retries} attempts: {e}")
                return []
            time.sleep(delay)

def post_json(path, payload, timeout=5):
    url = f"{API_BASE}{path}"
    try:
        return requests.post(url, json=payload, timeout=timeout)
    except RequestException as e:
        st.error(f"Failed to reach backend when saving: {e}")
        return None

def fetch_activities_for_category(category_id):
    all_activities = fetch_json("/activities/", retries=5, delay=1.0)
    return [a for a in all_activities if a.get("category_id") == category_id]

# -----------------------------
# Session state
# -----------------------------
if "selected_activity_ids" not in st.session_state:
    st.session_state.selected_activity_ids = {}

# -----------------------------
# Responsive CSS (improved)
# -----------------------------
RESPONSIVE_CSS = """
<style>
/* Base app font sizing (desktop) */
.stApp {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
  font-size: 15px;
  line-height: 1.2;
}

/* Card look */
.daylio-card {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e6e6e6;
  background: linear-gradient(180deg, #ffffff, #fbfbfb);
  margin-bottom: 12px;
}

/* Make Streamlit checkbox label fill the column and look like a chip */
.stCheckbox > label {
  display: block !important;
  width: 100% !important;
  padding: 8px 10px !important;
  border-radius: 18px !important;
  background: #f1f5f9 !important;
  border: 1px solid #e2e8f0 !important;
  color: #111827 !important;
  text-align: center !important;
  margin: 6px 0 !important;
  box-sizing: border-box !important;
  font-size: 14px !important;
}

/* When the checkbox is checked, Streamlit adds aria-checked; style via sibling selector */
.stCheckbox input[type="checkbox"]:checked + label {
  background: #0ea5a4 !important;
  color: #ffffff !important;
  border-color: #089e9c !important;
}

/* Remove extra padding around checkbox widget so chips align nicely */
.stCheckbox {
  margin: 0 !important;
  padding: 0 !important;
}

/* Make columns use full width and remove inner padding so chips span available space */
[data-testid="stVerticalBlock"] > div[role="list"] > div {
  padding: 0 !important;
}

/* Responsive scaling for smaller screens */
@media (max-width: 900px) {
  .stApp { font-size: 14px; }
  .stCheckbox > label { font-size: 13px !important; padding: 7px 8px !important; }
}
@media (max-width: 600px) {
  .stApp { font-size: 13px; }
  .stCheckbox > label { font-size: 12px !important; padding: 6px 6px !important; }
}

/* Make the card content use CSS grid so chips wrap and fill space when columns are 1 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  align-items: start;
}
</style>
"""
st.markdown(RESPONSIVE_CSS, unsafe_allow_html=True)

# -----------------------------
# Page UI
# -----------------------------
st.title("Log Your Mood")

with st.expander("Backend status"):
    health = fetch_json("/health", retries=2, delay=0.5)
    if isinstance(health, dict) and health.get("status") == "ok":
        st.success("Backend reachable")
    else:
        st.warning("Backend not reachable or returned unexpected response")

with st.spinner("Loading categories..."):
    categories = fetch_json("/categories/", retries=5, delay=1.0)

st.header("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)
note = st.text_area("Note (optional)")

# Sidebar layout control (user override)
st.sidebar.header("Layout")
cols_choice = st.sidebar.selectbox(
    "Columns per row for activity chips (override)",
    options=[1, 2, 3, 4, 5, 6],
    index=2,
    help="Choose how many columns to use. For phones choose 1 or 2."
)
st.sidebar.caption("Tip: set 1–2 for phones, 3–4 for tablets/desktop.")

st.subheader("What have you been up to?")

if not categories:
    st.info("No categories available. Add categories in Manage Categories.")
else:
    # Render each category as header + card
    for c in categories:
        cid = c.get("id")
        cname = c.get("name", f"Category {cid}")

        st.markdown(f"#### {cname}")
        st.markdown("<div class='daylio-card'>", unsafe_allow_html=True)

        acts = fetch_activities_for_category(cid)
        if not acts:
            st.info("No activities for this category. Add some in Manage Activities.")
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        # Ensure state exists
        if cid not in st.session_state.selected_activity_ids:
            st.session_state.selected_activity_ids[cid] = set()

        # Use a grid wrapper so chips fill available width when columns per row is 1
        st.markdown("<div class='card-grid'>", unsafe_allow_html=True)

        # Render checkboxes but place them inside columns to control layout on larger screens
        # We'll create N columns per row using st.columns, but the CSS above ensures labels fill width.
        cols_per_row = int(cols_choice) if cols_choice and cols_choice > 0 else 3
        # Render in rows of cols_per_row
        for i in range(0, len(acts), cols_per_row):
            row = acts[i : i + cols_per_row]
            cols = st.columns(cols_per_row)
            for j, a in enumerate(row):
                col = cols[j]
                aid = a.get("id")
                aname = a.get("name", f"Activity {aid}")
                checked = aid in st.session_state.selected_activity_ids[cid]
                cb_key = f"cb_{cid}_{aid}"
                # Checkbox widget (label styled to look like chip and fill width)
                val = col.checkbox(aname, value=checked, key=cb_key)
                if val and aid not in st.session_state.selected_activity_ids[cid]:
                    st.session_state.selected_activity_ids[cid].add(aid)
                if not val and aid in st.session_state.selected_activity_ids[cid]:
                    st.session_state.selected_activity_ids[cid].remove(aid)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Quick actions
st.markdown("---")
c1, c2, c3 = st.columns([1,1,2])
with c1:
    if st.button("Clear all selections"):
        st.session_state.selected_activity_ids = {}
        st.success("Cleared selections.")
with c2:
    if st.button("Clear empty categories"):
        st.session_state.selected_activity_ids = {k: v for k, v in st.session_state.selected_activity_ids.items() if v}
        st.success("Cleared empty category selections.")
with c3:
    st.caption("Select activities across categories. Use Clear to reset. Adjust Columns in the sidebar for layout.")

# Save
if st.button("Save"):
    selected_ids = []
    for ids in st.session_state.selected_activity_ids.values():
        selected_ids.extend(list(ids))

    payload = {
        "mood_score": mood_score,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "activity_ids": selected_ids,
    }

    with st.spinner("Saving entry..."):
        resp = post_json("/mood", payload)

    if resp is None:
        st.error("Could not send request to backend.")
    elif resp.ok:
        st.success("Saved mood entry.")
        st.session_state.selected_activity_ids = {}
    else:
        try:
            err = resp.json()
        except Exception:
            err = None
        if err and isinstance(err, dict) and err.get("detail"):
            st.error(f"Failed to save mood entry: {resp.status_code} — {err.get('detail')}")
        else:
            st.error(f"Failed to save mood entry: {resp.status_code}")
