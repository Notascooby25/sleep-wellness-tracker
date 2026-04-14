# frontend/pages/2_mood_entry.py
import streamlit as st
import requests
import time
from requests.exceptions import RequestException
from json import JSONDecodeError
import os

# Prefer environment variable if set (from .env via docker-compose); fallback to service name
API_BASE = os.getenv("API_BASE", "http://backend:8000")

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

def post_json(path, payload, timeout=5):
    url = f"{API_BASE}{path}"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r
    except RequestException as e:
        st.error(f"Failed to reach backend when saving: {e}")
        return None

# Page UI
st.title("Log Your Mood")

with st.expander("Backend status"):
    health = fetch_json("/health", retries=3, delay=0.5)
    if isinstance(health, dict) and health.get("status") == "ok":
        st.success("Backend reachable")
    else:
        st.warning("Backend not reachable or returned unexpected response")

# Load categories at runtime
categories = fetch_json("/categories", retries=5, delay=1.0)
category_options = [c.get("name", f"id:{c.get('id')}") for c in categories] if categories else []

st.header("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)
selected_category = st.selectbox("Category", ["(none)"] + category_options)
note = st.text_area("Note (optional)")

if st.button("Save"):
    payload = {
        "mood_score": mood_score,
        "note": note,
        "category": selected_category if selected_category != "(none)" else None
    }
    resp = post_json("/mood", payload)
    if resp is None:
        st.error("Could not send request to backend.")
    elif resp.ok:
        st.success("Saved mood entry.")
    else:
        st.error(f"Failed to save mood entry: {resp.status_code}")
