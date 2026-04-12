import streamlit as st
import requests
from datetime import datetime

BACKEND_URL = "http://backend:8000"  # docker-compose service name

st.title("Log Mood Entry")

# --- Input fields ---
mood_score = st.slider("Mood Score", min_value=1, max_value=5, value=3)
note = st.text_area("Note (optional)")
timestamp = st.datetime_input("Timestamp", value=datetime.now())

# --- Submit button ---
if st.button("Submit Mood Entry"):
    payload = {
        "timestamp": timestamp.isoformat(),
        "mood_score": mood_score,
        "note": note
    }

    try:
        response = requests.post(f"{BACKEND_URL}/mood/mood", json=payload)
        if response.status_code in (200, 201):
            st.success("Mood entry created successfully!")
        else:
            st.error(f"Error: {response.text}")
    except Exception as e:
        st.error(f"Request failed: {e}")

st.divider()

# --- Recent entries ---
st.subheader("Recent Mood Entries")

try:
    entries = requests.get(f"{BACKEND_URL}/mood").json()
    for entry in entries[::-1][:10]:  # show latest 10
        st.write(f"**{entry['timestamp']}** — Mood {entry['mood_score']}")
        if entry.get("note"):
            st.caption(entry["note"])
        st.write("---")
except Exception as e:
    st.error(f"Failed to load entries: {e}")
