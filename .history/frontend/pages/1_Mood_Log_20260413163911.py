import streamlit as st
import requests
from datetime import datetime

API_BASE = "http://backend:8000"  # internal Docker network


st.title("Log Your Mood")


# -------------------------
# Mood score
# -------------------------
st.subheader("How are you feeling?")
mood_score = st.slider("Mood (1 = great, 5 = rubbish)", 1, 5, 3)


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
    }