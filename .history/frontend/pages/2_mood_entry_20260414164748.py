# frontend/pages/2_mood_entry.py
import streamlit as st
import requests
import time
from requests.exceptions import RequestException
from json import JSONDecodeError

API_BASE = "http://backend:8000"

st.title("Log Your Mood")

def fetch_categories(retries=5, delay=1.0):
    url = f"{API_BASE}/categories"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, list):
                        return data
                    st.error("Unexpected categories format from backend.")
                    return []
                except JSONDecodeError:
                    st.error("Backend returned invalid JSON for categories.")
                    return []
            else:
                st.warning(f"Backend returned status {resp.status_code}")
                return []
        except RequestException as e:
            if attempt == retries:
                st.error(f"Failed to reach backend after {retries} attempts: {e}")
                return []
            time.sleep(delay)

# call fetch_categories inside the page runtime, not at import time
categories = fetch_categories()

category_options = [c.get("name", f"id:{c.get('id')}") for c in categories] if categories else []

st.header("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)
selected_category = st.selectbox("Category", ["(none)"] + category_options)
note = st.text_area("Note (optional)")

if st.button("Save"):
    try:
        r = requests.post(f"{API_BASE}/mood", json={
            "mood_score": mood_score,
            "note": note
        }, timeout=5)
        if r.ok:
            st.success("Saved mood entry.")
        else:
            st.error(f"Failed to save mood entry: {r.status_code}")
    except RequestException as e:
        st.error(f"Failed to reach backend when saving: {e}")
