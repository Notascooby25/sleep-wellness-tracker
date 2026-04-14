import streamlit as st
import requests

API_BASE = "http://backend:8000"

st.title("Mood Log")
st.subheader("Recent Mood Entries")

try:
    # Fetch all entries (correct endpoint)
    entries = requests.get(f"{API_BASE}/mood").json()

    # Sort newest → oldest
    entries = sorted(entries, key=lambda x: x["timestamp"], reverse=True)

    # Fetch activities so we can map IDs → names
    activities = requests.get(f"{API_BASE}/activities").json()
    activity_lookup = {a["id"]: a["name"] for a in activities}

    for e in entries:
        ts = e["timestamp"]
        mood = e["mood_score"]
        note = e.get("note", "")

        # Convert activity IDs → names
        act_names = [
            activity_lookup.get(aid, f"ID {aid}")
            for aid in e.get("activity_ids", [])
        ]
        act_display = ", ".join(act_names) if act_names else "None"

        st.markdown(f"**{ts} — Mood {mood}**")
        if note:
            st.write(f"Note: {note}")
        st.write(f"Activities: {act_display}")
        st.markdown("---")

except Exception as err:
    st.error(f"Failed to load entries: {err}")
