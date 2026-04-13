import streamlit as st
import requests
from datetime import datetime

API_BASE = "http://backend:8000"

st.title("Log Your Mood")

# -------------------------
# Mood score
# -------------------------
st.subheader("How are you feeling?")
mood_score = st.slider("Mood (1 = Great, 5 = Rubbish)", 1, 5, 3)

# -------------------------
# Fetch categories + activities
# -------------------------
categories = requests.get(f"{API_BASE}/categories").json()
activities = requests.get(f"{API_BASE}/activities").json()

# Organise activities by category
activities_by_cat = {}
for cat in categories:
    activities_by_cat[cat["id"]] = {
        "name": cat["name"],
        "activities": [a for a in activities if a["category_id"] == cat["id"]]
    }

# -------------------------
# Activity selection
# -------------------------
st.subheader("Activities")

selected_activity_ids = []

for cat_id, data in activities_by_cat.items():
    st.markdown(f"### {data['name']}")
    for act in data["activities"]:
        if st.checkbox(act["name"], key=f"act_{act['id']}"):
            selected_activity_ids.append(act["id"])

# -------------------------
# Notes
# -------------------------
st.subheader("Notes")
note = st.text_area("Write anything you want to remember", "")

# -------------------------
# Timestamp
# -------------------------
st.subheader("When did this happen?")
timestamp = st.datetime_input("Date & Time", datetime.now())

# -------------------------
# Submit
# -------------------------
if st.button("Log Entry"):
    payload = {
        "mood_score": mood_score,
        "note": note,
        "timestamp": timestamp.isoformat(),
        "activity_ids": selected_activity_ids
    }

    try:
        response = requests.post(f"{API_BASE}/mood/mood", json=payload)
        if response.status_code in (200, 201):
            st.success("Entry logged!")
        else:
            st.error(f"Error: {response.text}")
    except Exception as e:
        st.error(f"Request failed: {e}")
