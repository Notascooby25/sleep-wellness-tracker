import os
import streamlit as st
import requests
import time
from datetime import datetime, timezone
from requests.exceptions import RequestException
from json import JSONDecodeError

# Prefer environment variable (from .env via docker-compose)
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
                st.warning(f"Backend returned status {r.status_code}")
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
    all_activities = fetch_json("/activities", retries=5, delay=1.0)
    return [a for a in all_activities if a.get("category_id") == category_id]

# -----------------------------
# Session state for category selection
# -----------------------------
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None

# -----------------------------
# Page UI
# -----------------------------
st.title("Log Your Mood")

# Backend health check
with st.expander("Backend status"):
    health = fetch_json("/health", retries=3, delay=0.5)
    if isinstance(health, dict) and health.get("status") == "ok":
        st.success("Backend reachable")
    else:
        st.warning("Backend not reachable or returned unexpected response")

# -----------------------------
# Load categories
# -----------------------------
with st.spinner("Loading categories..."):
    categories = fetch_json("/categories", retries=5, delay=1.0)

st.header("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)

# -----------------------------
# Category selection (Option 3)
# -----------------------------
st.subheader("Category")

if categories:
    cols = st.columns(3)  # 3 buttons per row

    for idx, c in enumerate(categories):
        col = cols[idx % 3]

        # Highlight selected category
        is_selected = st.session_state.selected_category == c["id"]
        label = f"👉 {c['name']}" if is_selected else c["name"]

        if col.button(label):
            st.session_state.selected_category = c["id"]
else:
    st.info("No categories available.")

category_id = st.session_state.selected_category

# -----------------------------
# Load activities for selected category
# -----------------------------
activities_for_category = []
if category_id:
    activities_for_category = fetch_activities_for_category(category_id)

# -----------------------------
# Multi-select chips (Daylio style)
# -----------------------------
if activities_for_category:
    activity_names = [a["name"] for a in activities_for_category]
    selected_activities = st.multiselect(
        "Activities",
        activity_names,
        default=[],
        help="Select all activities that apply"
    )
else:
    selected_activities = []

note = st.text_area("Note (optional)")

# -----------------------------
# Save button
# -----------------------------
if st.button("Save"):
    # Convert selected activity names → IDs
    selected_activity_ids = [
        a["id"] for a in activities_for_category
        if a["name"] in selected_activities
    ]

    # Backend requires timestamp
    now_utc = datetime.now(timezone.utc).isoformat()

    payload = {
        "mood_score": mood_score,
        "note": note,
        "timestamp": now_utc,
        "activity_ids": selected_activity_ids
    }

    with st.spinner("Saving entry..."):
        resp = post_json("/mood", payload)

    if resp is None:
        st.error("Could not send request to backend.")
    elif resp.ok:
        st.success("Saved mood entry.")
    else:
        st.error(f"Failed to save mood entry: {resp.status_code}")
