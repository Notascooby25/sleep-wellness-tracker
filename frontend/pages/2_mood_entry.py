import os
import streamlit as st
import requests
import time
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

            # Success
            if r.status_code == 200:
                try:
                    return r.json()
                except JSONDecodeError:
                    st.error("Backend returned invalid JSON.")
                    return []

            # Non-200 response
            st.warning(f"Backend returned status {r.status_code}")
            return []

        except RequestException as e:
            # Final attempt → show error
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
# Load categories safely
# -----------------------------
with st.spinner("Loading categories..."):
    categories = fetch_json("/categories", retries=5, delay=1.0)

category_options = (
    [c.get("name", f"id:{c.get('id')}") for c in categories]
    if categories else []
)

# -----------------------------
# Mood entry form
# -----------------------------
st.header("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)
selected_category = st.selectbox("Category", ["(none)"] + category_options)
note = st.text_area("Note (optional)")

# -----------------------------
# Save button
# -----------------------------
if st.button("Save"):
    payload = {
        "mood_score": mood_score,
        "note": note,
        "category": selected_category if selected_category != "(none)" else None
    }

    with st.spinner("Saving entry..."):
        resp = post_json("/mood", payload)

    if resp is None:
        st.error("Could not send request to backend.")
    elif resp.ok:
        st.success("Saved mood entry.")
    else:
        st.error(f"Failed to save mood entry: {resp.status_code}")
