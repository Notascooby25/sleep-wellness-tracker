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
# Page UI
# -----------------------------
st.title("Mood Log")
st.subheader("Recent Mood Entries")

# Backend health check
with st.expander("Backend status"):
    health = fetch_json("/health", retries=3, delay=0.5)
    if isinstance(health, dict) and health.get("status") == "ok":
        st.success("Backend reachable")
    else:
        st.warning("Backend not reachable or returned unexpected response")

# -----------------------------
# Load mood entries
# -----------------------------
with st.spinner("Loading mood entries..."):
    entries = fetch_json("/mood", retries=5, delay=1.0)

if not entries:
    st.info("No mood entries found yet.")
    st.stop()

# Sort newest → oldest
entries = sorted(entries, key=lambda x: x.get("timestamp", ""), reverse=True)

# -----------------------------
# Load activities for ID → name mapping
# -----------------------------
with st.spinner("Loading activities..."):
    activities = fetch_json("/activities", retries=5, delay=1.0)

activity_lookup = {a["id"]: a["name"] for a in activities} if activities else {}

# -----------------------------
# Render entries
# -----------------------------
for e in entries:
    ts = e.get("timestamp", "Unknown time")
    mood = e.get("mood_score", "?")
    note = e.get("note", "")

    # Convert activity IDs → names
    act_ids = e.get("activity_ids", [])
    act_names = [activity_lookup.get(aid, f"ID {aid}") for aid in act_ids]
    act_display = ", ".join(act_names) if act_names else "None"

    st.markdown(f"### {ts}")
    st.write(f"**Mood:** {mood}")
    st.write(f"**Activities:** {act_display}")

    if note:
        st.write(f"**Note:** {note}")

    st.markdown("---")
