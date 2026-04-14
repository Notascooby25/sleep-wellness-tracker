import os
import streamlit as st
import requests
import time
from datetime import datetime, timezone
from requests.exceptions import RequestException
from json import JSONDecodeError

# Base API URL (use docker-compose env or fallback to localhost)
API_BASE = os.getenv("API_BASE", "http://backend:8000")

# -----------------------------
# Safe fetch helper with retries
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
                # Non-200 is not fatal for UI; return empty list so UI can handle it
                st.warning(f"Backend returned status {r.status_code} for {path}")
                return []
        except RequestException as e:
            if attempt == retries:
                st.error(f"Failed to reach backend after {retries} attempts: {e}")
                return []
            time.sleep(delay)

# -----------------------------
# Safe POST helper
# -----------------------------
def post_json(path, payload, timeout=5):
    url = f"{API_BASE}{path}"
    try:
        return requests.post(url, json=payload, timeout=timeout)
    except RequestException as e:
        st.error(f"Failed to reach backend when saving: {e}")
        return None

# -----------------------------
# Fetch activities for a category
# -----------------------------
def fetch_activities_for_category(category_id):
    all_activities = fetch_json("/activities/", retries=5, delay=1.0)
    return [a for a in all_activities if a.get("category_id") == category_id]

# -----------------------------
# Session state initialization
# -----------------------------
if "selected_activity_ids" not in st.session_state:
    # dict: { category_id: set(activity_id, ...) }
    st.session_state.selected_activity_ids = {}

if "focused_category" not in st.session_state:
    st.session_state.focused_category = None

# -----------------------------
# Page UI
# -----------------------------
st.title("Log Your Mood")

# Backend status (non-blocking)
with st.expander("Backend status"):
    health = fetch_json("/health", retries=2, delay=0.5)
    if isinstance(health, dict) and health.get("status") == "ok":
        st.success("Backend reachable")
    else:
        st.warning("Backend not reachable or returned unexpected response")

# Load categories
with st.spinner("Loading categories..."):
    categories = fetch_json("/categories/", retries=5, delay=1.0)

# Mood input
st.header("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)

# Note
note = st.text_area("Note (optional)")

# -----------------------------
# Category headers + activity cards
# -----------------------------
st.subheader("What have you been up to?")

if not categories:
    st.info("No categories available. Add categories in Manage Categories.")
else:
    # Render each category as a header with a card-like container for activities
    for c in categories:
        cid = c.get("id")
        cname = c.get("name", f"Category {cid}")

        # Category header
        st.markdown(f"### {cname}")

        # Card container (visual separation)
        with st.container():
            st.markdown("<div style='padding:8px;border-radius:8px;border:1px solid #eee;background:#fafafa'>", unsafe_allow_html=True)

            # Load activities for this category
            acts = fetch_activities_for_category(cid)

            if not acts:
                st.info("No activities for this category. Add some in Manage Activities.")
                st.markdown("</div>", unsafe_allow_html=True)
                continue

            # Ensure state exists for this category
            if cid not in st.session_state.selected_activity_ids:
                st.session_state.selected_activity_ids[cid] = set()

            # Layout: render activity chips as toggle buttons in rows
            cols_per_row = 4
            for i in range(0, len(acts), cols_per_row):
                row = acts[i : i + cols_per_row]
                cols = st.columns(cols_per_row)
                for j, a in enumerate(row):
                    col = cols[j]
                    aid = a.get("id")
                    aname = a.get("name", f"Activity {aid}")
                    is_selected = aid in st.session_state.selected_activity_ids[cid]

                    # Visual label: checkmark when selected
                    label = f"✓ {aname}" if is_selected else aname

                    # Use a unique key per activity button
                    key = f"act_btn_{cid}_{aid}"

                    if col.button(label, key=key):
                        # Toggle selection
                        if is_selected:
                            st.session_state.selected_activity_ids[cid].remove(aid)
                        else:
                            st.session_state.selected_activity_ids[cid].add(aid)

            st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# Quick actions: clear selections per category
# -----------------------------
st.markdown("---")
cols = st.columns([1, 1, 2])
with cols[0]:
    if st.button("Clear all selections"):
        st.session_state.selected_activity_ids = {}
        st.success("Cleared selections.")
with cols[1]:
    if st.button("Clear current category"):
        focused = st.session_state.get("focused_category")
        if focused and focused in st.session_state.selected_activity_ids:
            st.session_state.selected_activity_ids[focused] = set()
            st.success("Cleared selections for current category.")
        else:
            st.info("No focused category to clear.")
with cols[2]:
    st.caption("Tap activities to toggle selection. Use Clear to reset.")

# -----------------------------
# Save button
# -----------------------------
if st.button("Save"):
    # Collect selected IDs across all categories
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
        # Clear selections after successful save
        st.session_state.selected_activity_ids = {}
    else:
        # Show backend error code and any returned JSON message if available
        try:
            err = resp.json()
        except Exception:
            err = None
        if err and isinstance(err, dict) and err.get("detail"):
            st.error(f"Failed to save mood entry: {resp.status_code} — {err.get('detail')}")
        else:
            st.error(f"Failed to save mood entry: {resp.status_code}")
