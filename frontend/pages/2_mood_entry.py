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
                return []
        except RequestException:
            if attempt == retries:
                st.error("Backend unreachable.")
                return []
            time.sleep(delay)

def post_json(path, payload, timeout=5):
    url = f"{API_BASE}{path}"
    try:
        return requests.post(url, json=payload, timeout=timeout)
    except RequestException:
        st.error("Failed to reach backend when saving.")
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
# Sidebar toggle
# -----------------------------
st.sidebar.header("Display")
compact_mode = st.sidebar.checkbox("Compact mobile mode", value=False)

# -----------------------------
# CSS
# -----------------------------
BASE_CSS = """
<style>
.stApp {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial;
  font-size: 15px;
  line-height: 1.25;
}

.daylio-card {
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: #ffffff;
  margin-bottom: 14px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 8px;
  align-items: start;
}

.stCheckbox > label {
  display: block !important;
  width: 100% !important;
  padding: 8px 10px !important;
  border-radius: 18px !important;
  background: #f3f4f6 !important;
  border: 1px solid #e6e9ef !important;
  color: #0f172a !important;
  text-align: center !important;
  margin: 0 !important;
  font-size: 14px !important;
  font-weight: 500 !important;
}

.stCheckbox input[type="checkbox"]:checked + label {
  background: #0ea5a4 !important;
  color: #ffffff !important;
  border-color: #089e9c !important;
}

.stCheckbox {
  margin: 0 !important;
  padding: 0 !important;
}

@media (max-width: 900px) {
  .stApp { font-size: 14px; }
  .stCheckbox > label { font-size: 13px !important; padding: 7px 8px !important; }
  .card-grid { gap: 6px; }
}

@media (max-width: 600px) {
  .stApp { font-size: 13px; }
  .stCheckbox > label { font-size: 12px !important; padding: 6px 6px !important; }
  .card-grid { gap: 6px; }
}
</style>
"""

COMPACT_CSS = """
<style>
.stApp {
  font-size: 14px;
}

.daylio-card {
  padding: 6px;
  border-radius: 10px;
  border: 1px solid rgba(15, 23, 42, 0.05);
  background: #ffffff;
  margin-bottom: 10px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 4px;
  align-items: start;
}

.stCheckbox > label {
  padding: 4px 6px !important;
  font-size: 12px !important;
  border-radius: 14px !important;
  margin: 0 !important;
}

.stCheckbox input[type="checkbox"]:checked + label {
  background: #0ea5a4 !important;
  color: #ffffff !important;
  border-color: #089e9c !important;
}
</style>
"""

st.markdown(BASE_CSS, unsafe_allow_html=True)
if compact_mode:
    st.markdown(COMPACT_CSS, unsafe_allow_html=True)

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

st.subheader("What have you been up to?")

if not categories:
    st.info("No categories available.")
else:
    for c in categories:
        cid = c["id"]
        cname = c["name"]

        st.markdown(f"#### {cname}")
        st.markdown("<div class='daylio-card'>", unsafe_allow_html=True)

        acts = fetch_activities_for_category(cid)
        if not acts:
            st.info("No activities for this category.")
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        if cid not in st.session_state.selected_activity_ids:
            st.session_state.selected_activity_ids[cid] = set()

        st.markdown("<div class='card-grid'>", unsafe_allow_html=True)

        for a in acts:
            aid = a["id"]
            aname = a["name"]
            checked = aid in st.session_state.selected_activity_ids[cid]
            key = f"cb_{cid}_{aid}"

            val = st.checkbox(aname, value=checked, key=key)
            if val:
                st.session_state.selected_activity_ids[cid].add(aid)
            else:
                st.session_state.selected_activity_ids[cid].discard(aid)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# Quick actions
# -----------------------------
st.markdown("---")
c1, c2, c3 = st.columns([1, 1, 2])

with c1:
    if st.button("Clear all selections"):
        st.session_state.selected_activity_ids = {}
        st.success("Cleared selections.")

with c2:
    if st.button("Clear empty categories"):
        st.session_state.selected_activity_ids = {
            k: v for k, v in st.session_state.selected_activity_ids.items() if v
        }
        st.success("Cleared empty category selections.")

with c3:
    st.caption("Select activities across categories. Use Clear to reset.")

# -----------------------------
# Save
# -----------------------------
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
        except:
            err = None
        if err and isinstance(err, dict) and err.get("detail"):
            st.error(f"Failed to save mood entry: {resp.status_code} — {err['detail']}")
        else:
            st.error(f"Failed to save mood entry: {resp.status_code}")
