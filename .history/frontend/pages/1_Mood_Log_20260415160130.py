# frontend/pages/3_mood_log.py
import streamlit as st
import requests
import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

API_BASE = "http://backend:8000"
uk_tz = ZoneInfo("Europe/London")

st.set_page_config(page_title="Mood Log", layout="centered")

# -----------------------------
# Utilities
# -----------------------------
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
            label = dt.strftime("%A")  # Monday, Tuesday...
        else:
            label = dt.strftime("%A")  # fallback to weekday for consistency
    month = dt.strftime("%B")
    day_ord = _ordinal(dt.day)
    # include year only if not current year
    year_part = ""
    if dt.year != today.year:
        year_part = f", {dt.year}"
    return f"{label}, {month} {day_ord}{year_part}"

def parse_to_uk(dt_str: str) -> datetime.datetime:
    """
    Parse ISO timestamp string to a timezone-aware datetime in Europe/London.
    Handles timezone-aware ISO strings and naive ISO strings (assume UTC).
    """
    try:
        dt = datetime.datetime.fromisoformat(dt_str)
    except Exception:
        # fallback: try common format without microseconds
        try:
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            # last resort: current time
            dt = datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(uk_tz)

# -----------------------------
# Data fetching
# -----------------------------
@st.cache_data(ttl=30)
def fetch_activities():
    try:
        r = requests.get(f"{API_BASE}/activities/")
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

@st.cache_data(ttl=15)
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

# -----------------------------
# Render logic
# -----------------------------
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
            notes = ent.get("notes", "")
            activity_ids = ent.get("activity_ids", []) or []

            # Map activity ids to names
            activity_names = [activity_map.get(aid, str(aid)) for aid in activity_ids]

            # Entry header row
            cols = st.columns([1, 4, 2])
            with cols[0]:
                st.markdown(f"**{time_str}**")
            with cols[1]:
                st.markdown(f"**Mood {mood}**")
                if notes:
                    st.write(notes)
            with cols[2]:
                if activity_names:
                    st.markdown("**Activities**")
                    st.write(", ".join(activity_names))
                else:
                    st.write("")

            st.markdown("---")

# -----------------------------
# Controls and render call
# -----------------------------
st.markdown("# Mood Log")
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Refresh"):
        # clear caches and re-run
        fetch_entries.clear()
        fetch_activities.clear()
        st.experimental_rerun()
with col2:
    st.write("Entries are shown in UK local time (Europe/London).")

render_mood_log(entries)
