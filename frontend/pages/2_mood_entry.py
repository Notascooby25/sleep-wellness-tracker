# frontend/pages/2_mood_entry.py
import os
import streamlit as st
import requests
import time
from datetime import datetime, timezone
from requests.exceptions import RequestException
from json import JSONDecodeError
from streamlit.components.v1 import html as st_html

# Base API URL
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
                # Non-200: return empty so UI can handle gracefully
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
    st.session_state.selected_activity_ids = {}  # { category_id: set(activity_ids) }

# -----------------------------
# Auto-detect viewport width (one-time)
# -----------------------------
# This small snippet will reload the page once and append ?cols=N to the URL.
# It only runs if the URL doesn't already contain a cols param.
# This avoids needing complex JS <-> Streamlit state plumbing.
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
  } catch (e) {
    // fail silently
  }
})();
</script>
"""
# Inject the JS. It will redirect once if needed.
st_html(AUTO_JS, height=0)

# Read query params (set by the JS redirect) and allow sidebar override
query_params = st.experimental_get_query_params()
detected_cols = int(query_params.get("cols", [3])[0])

# Sidebar controls
st.sidebar.header("Layout")
cols_choice_override = st.sidebar.selectbox(
    "Columns per row (override auto)",
    options=[None, 1, 2, 3, 4, 5, 6],
    index=0,
    format_func=lambda x: "Auto" if x is None else str(x),
    help="Choose how many columns to use for activity chips. 'Auto' uses detected viewport width."
)
# Final columns per row
cols_per_row = int(cols_choice_override) if cols_choice_override else detected_cols

# -----------------------------
# Styling (responsive + grid)
# -----------------------------
STYLES = f"""
<style>
/* App base font and smoothing */
.stApp {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: 15px;
  line-height: 1.25;
}}

/* Category card */
.daylio-card {{
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, #ffffff, #fcfcfd);
  margin-bottom: 14px;
}}

/* Grid wrapper for chips */
.card-grid {{
  display: grid;
  grid-template-columns: repeat({cols_per_row}, 1fr);
  gap: 8px;
  align-items: start;
}}

/* Make Streamlit checkbox label look like a chip and fill its grid cell */
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

/* Responsive font scaling */
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

# Load categories
with st.spinner("Loading categories..."):
    categories = fetch_json("/categories/", retries=5, delay=1.0)

# Mood + note
st.header("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)
note = st.text_area("Note (optional)")

# -----------------------------
# Category headers + activity cards (grid)
# -----------------------------
st.subheader("What have you been up to?")

if not categories:
    st.info("No categories available. Add categories in Manage Categories.")
else:
    for c in categories:
        cid = c.get("id")
        cname = c.get("name", f"Category {cid}")

        # Category header
        st.markdown(f"#### {cname}")

        # Card wrapper
        st.markdown("<div class='daylio-card'>", unsafe_allow_html=True)

        acts = fetch_activities_for_category(cid)
        if not acts:
            st.info("No activities for this category. Add some in Manage Activities.")
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        # Ensure state exists
        if cid not in st.session_state.selected_activity_ids:
            st.session_state.selected_activity_ids[cid] = set()

        # Grid wrapper
        st.markdown("<div class='card-grid'>", unsafe_allow_html=True)

        # Render checkboxes sequentially (CSS grid will place them)
        # We render them in a single column flow so the grid CSS controls layout.
        for a in acts:
            aid = a.get("id")
            aname = a.get("name", f"Activity {aid}")
            checked = aid in st.session_state.selected_activity_ids[cid]
            cb_key = f"cb_{cid}_{aid}"
            # Use st.checkbox; label styling makes it look like a chip and fill the grid cell
            val = st.checkbox(aname, value=checked, key=cb_key)
            if val and aid not in st.session_state.selected_activity_ids[cid]:
                st.session_state.selected_activity_ids[cid].add(aid)
            if not val and aid in st.session_state.selected_activity_ids[cid]:
                st.session_state.selected_activity_ids[cid].remove(aid)

        st.markdown("</div>", unsafe_allow_html=True)  # close grid
        st.markdown("</div>", unsafe_allow_html=True)  # close card

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
        st.session_state.selected_activity_ids = {k: v for k, v in st.session_state.selected_activity_ids.items() if v}
        st.success("Cleared empty category selections.")
with c3:
    st.caption("Select activities across categories. Use Clear to reset. Use the sidebar to override columns.")

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
        except Exception:
            err = None
        if err and isinstance(err, dict) and err.get("detail"):
            st.error(f"Failed to save mood entry: {resp.status_code} — {err.get('detail')}")
        else:
            st.error(f"Failed to save mood entry: {resp.status_code}")
What I changed and why
Auto viewport detection: small JS runs once and appends ?cols=N to the URL so the page knows how many columns to use for the grid. This avoids fragile JS ↔ Streamlit state hacks and keeps behavior predictable.

CSS grid: .card-grid uses repeat({cols}, 1fr) so chips fill the available width and form multiple columns on mobile when cols is 1–3.

Checkbox labels styled as chips: we style .stCheckbox > label to be block elements that fill their grid cell; checked state shows the Daylio‑like colored chip.

Card visuals: subtle border and gradient to mimic Daylio cards without heavy backgrounds.

Multi‑select across categories: unchanged logic — selections are stored per category in st.session_state.selected_activity_ids.

Quick testing checklist
Open the page in your iPhone browser inspector (or real phone). The page will reload once to set cols.

If chips still look cramped, open the sidebar and set Columns per row to 1 or 2.

Select multiple activities across different categories and press Save. Confirm /mood contains all selected activity_ids.

Add/rename/delete categories and activities in Manage pages and refresh this page — lists should update.

If you still see gaps or card issues
Tell me the exact device width shown in the inspector (px) and a screenshot of the page. I’ll tune the cols thresholds and CSS min widths so chips always fill the row.

If you want an even closer pixel match to Daylio (rounded icon chips, tighter spacing, different font weight), I can produce a custom HTML chip grid that looks identical — it requires a small hidden Streamlit input to keep selection state in sync; I can provide that next.

Which do you want next: tweak thresholds for your phone width, or pixel‑perfect HTML chips?



still gaps, as on laptop, i cannot test with my phone, but this should replicate it on a phone
Plan
Make the chip grid auto‑fit columns so chips always fill available width (grid-template-columns: repeat(auto-fit, minmax(100px, 1fr))).

Force checkbox labels to be block elements that fill their grid cell and remove Streamlit widget margins that create gaps.

Reduce chip padding and font sizes at small breakpoints so more chips fit per row.

Keep checkboxes (stable multi‑select) and st.session_state selection logic unchanged.

Provide a sidebar override for columns if you want to force a layout for testing.

Below is a drop‑in frontend/pages/2_mood_entry.py that implements these changes. Paste it over your current file and reload the app. It uses CSS grid with auto-fit so the chips will expand to fill the row on mobile emulation and real phones.

python
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
How this fixes the gaps
grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)) makes the grid auto‑fit as many columns as will comfortably fit; each chip expands to fill its column. On narrow screens the grid will create fewer columns and each chip will stretch to fill the width, eliminating gaps.

Styling .stCheckbox > label to display:block and width:100% forces each checkbox label to occupy the full grid cell.

Reduced padding and font sizes at small breakpoints let more chips fit per row.

Quick testing steps (desktop mobile emulation)
Paste the file and reload the Streamlit app.

Open Chrome DevTools → Toggle device toolbar → choose an iPhone/Android preset (e.g., iPhone 12).

Reload the page (the JS redirect runs once to set cols).

If chips still look cramped, open the sidebar and set Columns per row (override) to 1 or 2 to force stacking.

Select multiple activities across categories and press Save; verify /mood contains all selected activity_ids.

If you still see gaps
Tell me the exact device width (px) shown in the inspector and paste a screenshot of the page. I’ll tune the minmax(100px, 1fr) value (try minmax(80px, 1fr) or minmax(120px, 1fr)) to match your target device.

If you want a pixel‑perfect Daylio look (rounded icon chips, tighter spacing, exact font weights), I can replace checkboxes with a custom HTML chip grid and keep selection state in sync via a hidden Streamlit input. That will remove Streamlit widget wrapping and give full control over layout — I can provide that next if you want the absolute closest match.

AttributeError: module 'streamlit' has no attribute 'experimental_get_query_params'

File "/app/pages/2_mood_entry.py", line 78, in <module>
    query_params = st.experimental_get_query_params()
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Thanks — the error comes from using a Streamlit experimental API that isn’t available in your runtime. I removed the query‑param JS + the experimental_get_query_params call and simplified the layout so the grid auto‑fits to the viewport using pure CSS. That eliminates the redirect and avoids any Streamlit experimental APIs while still making chips fill available space on mobile emulation.

Below is a drop‑in frontend/pages/2_mood_entry.py that:

Removes st.experimental_get_query_params and the JS redirect.

Uses CSS grid auto-fit + minmax so chips expand to fill the row on phones and laptops.

Keeps checkbox chips for stable multi‑select across categories.

Keeps resilient API helpers and timestamp in the payload.

Adds a sidebar override to force columns if you want to test different layouts.

Paste this file over your current 2_mood_entry.py and reload the app.

python
# frontend/pages/2_mood_entry.py
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
    st.session_state.selected_activity_ids = {}  # { category_id: set(activity_ids) }

# -----------------------------
# Responsive CSS (auto-fit grid)
# -----------------------------
STYLES = """
<style>
/* Base font and smoothing */
.stApp {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: 15px;
  line-height: 1.25;
}

/* Category card */
.daylio-card {
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, #ffffff, #fcfcfd);
  margin-bottom: 14px;
}

/* Grid wrapper: auto-fit so chips fill available space */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
  align-items: start;
}

/* Make Streamlit checkbox label fill the grid cell and look like a chip */
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
  box-sizing: border-box !important;
  font-size: 14px !important;
  font-weight: 500 !important;
}

/* Checked state */
.stCheckbox input[type="checkbox"]:checked + label {
  background: #0ea5a4 !important;
  color: #ffffff !important;
  border-color: #089e9c !important;
}

/* Remove extra spacing around checkbox widget */
.stCheckbox {
  margin: 0 !important;
  padding: 0 !important;
}

/* Reduce margins Streamlit adds around vertical blocks */
[data-testid="stVerticalBlock"] > div[role="list"] > div {
  padding: 0 !important;
}

/* Responsive font scaling and chip sizing */
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

# Sidebar override for testing layout
st.sidebar.header("Layout")
cols_override = st.sidebar.selectbox(
    "Force columns per row (optional)",
    options=[None, 1, 2, 3, 4, 5, 6],
    index=0,
    format_func=lambda x: "Auto" if x is None else str(x),
    help="Choose a forced column count for testing. Leave Auto for responsive behavior."
)

# If user forces columns, adjust the grid min width to approximate that layout
# (we do this by changing the minmax value used by the grid)
min_width = 100
if cols_override:
    try:
        cols_int = int(cols_override)
        # approximate min width so repeat(auto-fit, minmax(min_width,1fr)) yields desired columns on typical widths
        # assume typical container width ~ 1000px; compute min_width = floor(1000 / cols)
        approx_container = 1000
        min_width = max(70, int(approx_container / cols_int) - 8)
    except Exception:
        min_width = 100

# If user forced columns, inject a small style override to change minmax
if cols_override:
    override_css = f"""
    <style>
    .card-grid {{
      grid-template-columns: repeat(auto-fit, minmax({min_width}px, 1fr));
    }}
    </style>
    """
    st.markdown(override_css, unsafe_allow_html=True)

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
    st.caption("Select activities across categories. Use Clear to reset. Use the sidebar to override columns for testing.")

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
            st.error(f"Failed to save mood entry: {resp.status_code}"