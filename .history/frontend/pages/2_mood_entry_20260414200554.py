# frontend/pages/2_mood_entry.py
import os
import streamlit as st
import requests
import time
from datetime import datetime, timezone
from requests.exceptions import RequestException
from json import JSONDecodeError
from streamlit.components.v1 import html as st_html

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
# Auto-detect viewport width (one-time)
# -----------------------------
AUTO_JS = """
<script>
(function(){
  try {
    const params = new URLSearchParams(window.location.search);
    if (!params.has('cols')) {
      const w = window.innerWidth || document.documentElement.clientWidth;
      let cols = 3;
      if (w < 420) cols = 1;
      else if (w < 700) cols = 2;
      else if (w < 1000) cols = 3;
      else cols = 4;
      params.set('cols', cols);
      const newUrl = window.location.pathname + '?' + params.toString();
      window.location.replace(newUrl);
    }
  } catch (e) {}
})();
</script>
"""
st_html(AUTO_JS, height=0)

query_params = st.experimental_get_query_params()
detected_cols = int(query_params.get("cols", [3])[0])

# Sidebar override
st.sidebar.header("Layout")
cols_choice_override = st.sidebar.selectbox(
    "Columns per row (override auto)",
    options=[None, 1, 2, 3, 4, 5, 6],
    index=0,
    format_func=lambda x: "Auto" if x is None else str(x),
)
cols_per_row = int(cols_choice_override) if cols_choice_override else detected_cols

# -----------------------------
# Improved responsive CSS
# -----------------------------
STYLES = f"""
<style>
/* Base font */
.stApp {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: 15px;
  line-height: 1.25;
}}

/* Card look */
.daylio-card {{
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, #ffffff, #fcfcfd);
  margin-bottom: 14px;
}}

/* Grid wrapper: auto-fit so chips fill available space */
.card-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
  align-items: start;
}}

/* Make Streamlit checkbox label fill the grid cell and look like a chip */
.stCheckbox > label {{
  display: block !important;
  width: 100% !important;
  padding: 8px 10px !important;
  border-radius: 18px !important;
  background: #f3f4f6 !important;
  border: 1px solid #e6e9ef !important;
  color: #0f172a !important;
  text-align: center !important;
  margin: 0 !important;
  box-sizing: border-box !important;
  font-size: 14px !important;
  font-weight: 500 !important;
}}

/* Checked state */
.stCheckbox input[type="checkbox"]:checked + label {{
  background: #0ea5a4 !important;
  color: #ffffff !important;
  border-color: #089e9c !important;
}}

/* Remove extra spacing around checkbox widget */
.stCheckbox {{
  margin: 0 !important;
  padding: 0 !important;
}}

/* Reduce margins Streamlit adds around vertical blocks */
[data-testid="stVerticalBlock"] > div[role="list"] > div {{
  padding: 0 !important;
}}

/* Responsive font scaling and chip sizing */
@media (max-width: 900px) {{
  .stApp {{ font-size: 14px; }}
  .stCheckbox > label {{ font-size: 13px !important; padding: 7px 8px !important; }}
  .card-grid {{ gap: 6px; }}
}}
@media (max-width: 600px) {{
  .stApp {{ font-size: 13px; }}
  .stCheckbox > label {{ font-size: 12px !important; padding: 6px 6px !important; }}
  .card-grid {{ gap: 6px; }}
}}
</style>
"""
st.markdown(STYLES, unsafe_allow_html=True)

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
    st.info("No categories available. Add categories in Manage Categories.")
else:
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

        if cid not in st.session_state.selected_activity_ids:
            st.session_state.selected_activity_ids[cid] = set()

        # Grid wrapper: auto-fit columns will fill available width
        st.markdown("<div class='card-grid'>", unsafe_allow_html=True)

        # Render checkboxes sequentially; CSS grid will place them into columns
        for a in acts:
            aid = a.get("id")
            aname = a.get("name", f"Activity {aid}")
            checked = aid in st.session_state.selected_activity_ids[cid]
            cb_key = f"cb_{cid}_{aid}"
            val = st.checkbox(aname, value=checked, key=cb_key)
            if val and aid not in st.session_state.selected_activity_ids[cid]:
                st.session_state.selected_activity_ids[cid].add(aid)
            if not val and aid in st.session_state.selected_activity_ids[cid]:
                st.session_state.selected_activity_ids[cid].remove(aid)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Quick actions
st.markdown("---")
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("Clear all selections"):
        st.session_state.selected_activity_ids = {}
        st.success("Cleared selections.")
with c2:
    if st.button("Clear empty categories"):
        st.session_state.selected_activity_ids = {k: v for k, v in st.session_state.selected_activity_ids.items() if v}
        st.success("Cleared empty category selections.")
with c3:
    st.caption("Select activities across categories. Use Clear to reset. Use the sidebar to override columns.")

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
