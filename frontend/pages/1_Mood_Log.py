# frontend/pages/1_mood_log.py
import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

API_BASE = "http://backend:8000"
uk_tz = ZoneInfo("Europe/London")

st.set_page_config(page_title="Mood Log", layout="centered")

def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

def format_date_heading(dt: datetime.date, today: datetime.date) -> str:
    if dt == today:
        label = "Today"
    elif dt == (today - datetime.timedelta(days=1)):
        label = "Yesterday"
    else:
        days_diff = (today - dt).days
        if 1 < days_diff <= 6:
            label = dt.strftime("%A")
        else:
            label = dt.strftime("%A")
    month = dt.strftime("%B")
    day_ord = _ordinal(dt.day)
    year_part = ""
    if dt.year != today.year:
        year_part = f", {dt.year}"
    return f"{label}, {month} {day_ord}{year_part}"

def parse_to_uk(dt_str: str) -> datetime.datetime:
    try:
        dt = datetime.datetime.fromisoformat(dt_str)
    except Exception:
        try:
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            dt = datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(uk_tz)

def fetch_activities():
    try:
        r = requests.get(f"{API_BASE}/activities/")
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def fetch_entries():
    try:
        r = requests.get(f"{API_BASE}/mood/")
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

activities = fetch_activities()
activity_map = {a["id"]: a["name"] for a in activities}

entries = fetch_entries()

# Debug raw entries (remove when confirmed)
st.markdown("## Raw backend entries (debug)")
st.write(entries)

def render_mood_log(entries_list):
    if not entries_list:
        st.info("No mood entries yet.")
        return

    grouped = defaultdict(list)
    for e in entries_list:
        ts = e.get("timestamp")
        if not ts:
            continue
        try:
            local_dt = parse_to_uk(ts)
        except Exception:
            continue
        e["_local_dt"] = local_dt
        e["_local_date"] = local_dt.date()
        grouped[e["_local_date"]].append(e)

    sorted_dates = sorted(grouped.keys(), reverse=True)
    today = datetime.datetime.now(uk_tz).date()

    for d in sorted_dates:
        heading = format_date_heading(d, today)
        st.markdown(f"### {heading}")

        day_entries = sorted(grouped[d], key=lambda x: x["_local_dt"], reverse=True)

        for ent in day_entries:
            dt = ent["_local_dt"]
            time_str = dt.strftime("%H:%M")
            mood = ent.get("mood_score", ent.get("mood", "—"))
            # Prefer backend 'note', fall back to frontend 'notes'
            notes = ent.get("note")
            if notes is None:
                notes = ent.get("notes", "")
            activity_ids = ent.get("activity_ids", []) or []
            activity_names = [activity_map.get(aid, str(aid)) for aid in activity_ids]

            cols = st.columns([1, 4, 3])
            with cols[0]:
                st.markdown(f"**{time_str}**")
            with cols[1]:
                st.markdown(f"**Mood {mood}**")
                if notes:
                    st.write(notes)
                else:
                    st.write("_No notes_")
            with cols[2]:
                if activity_names:
                    st.markdown("**Activities**")
                    st.write(", ".join(activity_names))
                else:
                    st.write("")

            st.markdown("---")

st.markdown("# Mood Log")
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Refresh"):
        st.session_state["_force_rerun_counter"] = st.session_state.get("_force_rerun_counter", 0) + 1
        try:
            st.experimental_rerun()
        except Exception:
            st.session_state["_refresh_trigger"] = st.session_state.get("_refresh_trigger", 0) + 1
with col2:
    st.write("Entries are shown in UK local time (Europe/London).")

render_mood_log(entries)
