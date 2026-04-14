import os
import json
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
# Sidebar
# -----------------------------
st.sidebar.header("Display")
compact_mode = st.sidebar.checkbox("Compact mobile mode", value=False)

# -----------------------------
# CSS (Base + Compact + Animation)
# -----------------------------
CSS = f"""
<style>
:root {{
  --chip-bg: #f3f4f6;
  --chip-border: #e6e9ef;
  --chip-text: #0f172a;

  --chip-selected-bg: #0ea5a4;
  --chip-selected-text: #ffffff;
  --chip-selected-border: #089e9c;
}}

.chip-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax({80 if compact_mode else 110}px, 1fr));
  gap: {4 if compact_mode else 8}px;
  margin-top: 6px;
}}

.chip {{
  background: var(--chip-bg);
  border: 1px solid var(--chip-border);
  color: var(--chip-text);
  padding: {4 if compact_mode else 8}px {6 if compact_mode else 10}px;
  border-radius: {14 if compact_mode else 18}px;
  font-size: {12 if compact_mode else 14}px;
  font-weight: 500;
  text-align: center;
  cursor: pointer;
  transition: all 0.12s ease-out;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  user-select: none;
}}

.chip.selected {{
  background: var(--chip-selected-bg);
  color: var(--chip-selected-text);
  border-color: var(--chip-selected-border);
  box-shadow: 0 2px 6px rgba(14,165,164,0.35);
  transform: scale(1.05);
}}

.chip:active {{
  transform: scale(1.05);
  box-shadow: 0 2px 6px rgba(14,165,164,0.35);
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -----------------------------
# JS for chip toggle
# -----------------------------
JS = """
<script>
function initChipLogic() {
    const chips = document.querySelectorAll('.chip');
    const hiddenInput = document.getElementById('selected_ids_input');

    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            chip.classList.toggle('selected');

            const selected = Array.from(document.querySelectorAll('.chip.selected'))
                .map(c => c.dataset.id);

            hiddenInput.value = JSON.stringify(selected);
            hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
        });
    });
}
setTimeout(initChipLogic, 100);
</script>
"""
st_html(JS, height=0)

# -----------------------------
# Hidden input for chip state
# -----------------------------
selected_ids_json = st.text_input("selected_ids_input", "[]", key="selected_ids_input")

try:
    selected_ids = set(json.loads(selected_ids_json))
except:
    selected_ids = set()

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

        st.markdown("<div class='chip-grid'>", unsafe_allow_html=True)

        for a in acts:
            aid = str(a["id"])
            aname = a["name"]
            selected_class = "selected" if aid in selected_ids else ""
            st.markdown(
                f"<button class='chip {selected_class}' data-id='{aid}'>{aname}</button>",
                unsafe_allow_html=True
            )

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# Save
# -----------------------------
if st.button("Save"):
    payload = {
        "mood_score": mood_score,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "activity_ids": list(selected_ids),
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
