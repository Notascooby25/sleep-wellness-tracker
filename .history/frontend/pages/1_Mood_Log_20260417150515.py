import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo

API_BASE = "http://backend:8000"

st.set_page_config(page_title="Mood Log", layout="centered")

st.title("Mood Log")
st.caption("Entries are shown in UK local time (Europe/London).")

uk_tz = ZoneInfo("Europe/London")

# Colour map for 1–5 scale
def mood_colour(score):
    colours = {
        1: "#2ecc71",   # green (great)
        2: "#a3e635",   # lime
        3: "#facc15",   # amber
        4: "#f97316",   # orange
        5: "#ef4444",   # red (rubbish)
    }
    return colours.get(score, "#999999")

# Fetch entries
def load_entries():
    try:
        r = requests.get(f"{API_BASE}/mood/")
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

entries = load_entries()

# Group by date
grouped = {}
for e in entries:
    ts = datetime.datetime.fromisoformat(e["timestamp"]).astimezone(uk_tz)
    date_key = ts.date()
    if date_key not in grouped:
        grouped[date_key] = []
    grouped[date_key].append((ts, e))

# Sort newest → oldest
sorted_days = sorted(grouped.keys(), reverse=True)

# Divider style
DIVIDER = "<hr style='margin: 10px 0; opacity: 0.25;'>"

for day in sorted_days:
    day_label = day.strftime("%A, %B %d")
    st.markdown(f"### {day_label}")

    # Sort entries newest → oldest
    day_entries = sorted(grouped[day], key=lambda x: x[0], reverse=True)

    for idx, (ts, e) in enumerate(day_entries):
        mood = e["mood_score"]
        notes = e.get("notes") or "No notes"
        acts = e.get("activities", [])

        colour = mood_colour(mood)

        # Compact card
        st.markdown(
            f"""
            <div style='padding: 8px 12px; border-radius: 8px; background: #fafafa;'>
                <div style='font-size: 14px; opacity: 0.7;'>{ts.strftime("%H:%M")}</div>
                <div style='font-size: 18px; font-weight: 600; color:{colour};'>
                    Mood {mood}
                </div>
                <div style='margin-top: 4px; font-size: 14px;'>{notes}</div>
            """,
            unsafe_allow_html=True,
        )

        # Activities
        if acts:
            act_names = ", ".join(a["name"] for a in acts)
            st.markdown(
                f"<div style='font-size: 13px; margin-top: 4px;'><b>Activities:</b> {act_names}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

        # Divider between entries
        if idx < len(day_entries) - 1:
            st.markdown(DIVIDER, unsafe_allow_html=True)
