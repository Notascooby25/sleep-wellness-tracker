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
        if response.status_code in (200, 201