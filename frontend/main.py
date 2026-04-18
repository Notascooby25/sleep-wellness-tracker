import streamlit as st
import requests

st.set_page_config(page_title="Sleep Wellness Tracker", layout="centered")

# Make Mood Entry the first page users see when opening the app root.
try:
    st.switch_page("pages/2_mood_entry.py")
    st.stop()
except Exception:
    pass

st.title("Sleep Wellness Tracker")

# Simple backend health check
try:
    r = requests.get("http://backend:8000/health", timeout=2)
    status = r.json().get("status", "unknown")
    st.success(f"Backend status: {status}")
except Exception:
    st.error("Backend not reachable yet.")
