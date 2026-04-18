import streamlit as st
import requests
import datetime
import html
from zoneinfo import ZoneInfo

API_BASE = "http://backend:8000"

st.set_page_config(page_title="Mood Log", layout="wide")

st.markdown(
    """
<style>
:root {
    --bg-soft: #f4f7fb;
    --card-bg: #ffffff;
    --card-border: #d9e2ef;
    --text-main: #132238;
    --text-sub: #5f6f84;
    --chip-bg: #ecf2fb;
    --chip-text: #1f4066;
}

[data-testid="stAppViewContainer"] {
    background:
      radial-gradient(900px 260px at 8% -12%, #dbeafe 0%, transparent 45%),
      radial-gradient(900px 280px at 92% -18%, #e5f4ff 0%, transparent 42%),
      linear-gradient(180deg, #f9fbff 0%, #f2f6fc 100%);
}

.block-container {
    max-width: 1120px;
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}

.hero {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
    margin-bottom: 14px;
}

.hero h1 {
    margin: 0;
    color: var(--text-main);
    letter-spacing: 0.2px;
    font-size: 1.85rem;
    line-height: 1.15;
}

.hero p {
    margin: 8px 0 0;
    color: var(--text-sub);
    font-size: 0.96rem;
}

.day-header {
    margin-top: 1rem;
    margin-bottom: 0.7rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
}

.day-title {
    margin: 0;
    color: var(--text-main);
    font-size: 1.1rem;
    font-weight: 700;
}

.count-pill {
    color: #25466f;
    background: #e4eefb;
    border: 1px solid #c9dbf4;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    padding: 0.24rem 0.6rem;
    white-space: nowrap;
}

.entry-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 12px 13px;
    margin-bottom: 0.7rem;
    box-shadow: 0 6px 14px rgba(30, 58, 138, 0.06);
}

.entry-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
}

.time-tag {
    font-weight: 700;
    color: #355271;
    background: #eef4fb;
    border: 1px solid #d8e6f6;
    border-radius: 8px;
    padding: 0.2rem 0.48rem;
    font-size: 0.74rem;
}

.mood-pill {
    border-radius: 999px;
    padding: 0.22rem 0.68rem;
    font-size: 0.76rem;
    font-weight: 700;
    color: #0f172a;
    white-space: nowrap;
}

.entry-notes {
    margin-top: 0.55rem;
    color: var(--text-main);
    line-height: 1.4;
    font-size: 0.94rem;
    min-height: 1.1rem;
}

.chip-wrap {
    margin-top: 0.62rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
}

.chip {
    display: inline-flex;
    align-items: center;
    gap: 0.34rem;
    background: var(--chip-bg);
    color: var(--chip-text);
    border: 1px solid #ccddf4;
    border-radius: 999px;
    padding: 0.14rem 0.55rem;
    font-size: 0.74rem;
    font-weight: 600;
}

.chip-dot {
    font-size: 0.86rem;
    line-height: 1;
    opacity: 0.9;
}

.empty-note {
    color: #7d8ea4;
    font-style: italic;
}

.empty-state {
    padding: 1rem;
    border: 1px dashed #c8d7ea;
    border-radius: 12px;
    color: #496685;
    background: #f8fbff;
    font-weight: 500;
}

@media (max-width: 860px) {
    .block-container {
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }

    .hero h1 {
        font-size: 1.55rem;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
    <h1>Mood Log</h1>
    <p>Entries are shown in UK local time (Europe/London).</p>
</div>
""",
    unsafe_allow_html=True,
)

uk_tz = ZoneInfo("Europe/London")

MOOD_META = {
    1: ("Great", "#b8f0cf"),
    2: ("Good", "#d9efb3"),
    3: ("Okay", "#fde58a"),
    4: ("Low", "#f7c597"),
    5: ("Rubbish", "#f5a6a6"),
}


def mood_meta(score):
    return MOOD_META.get(score, (f"{score}", "#d1d5db"))


@st.cache_data(ttl=45, show_spinner=False)
def load_entries():
    try:
        r = requests.get(f"{API_BASE}/mood/", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def load_activities():
    try:
        r = requests.get(f"{API_BASE}/activities/", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


toolbar_col, refresh_col = st.columns([0.8, 0.2])
with toolbar_col:
    st.caption("Use refresh if entries were added from another device a moment ago.")
with refresh_col:
    if st.button("Refresh", use_container_width=True):
        load_entries.clear()
        load_activities.clear()
        st.rerun()


entries = load_entries()
activities_list = load_activities()
activity_lookup = {a["id"]: a["name"] for a in activities_list}


# Group entries by date
grouped = {}
for e in entries:
    ts = datetime.datetime.fromisoformat(e["timestamp"]).astimezone(uk_tz)
    date_key = ts.date()
    if date_key not in grouped:
        grouped[date_key] = []
    grouped[date_key].append((ts, e))

# Sort newest → oldest
sorted_days = sorted(grouped.keys(), reverse=True)

if not sorted_days:
    st.markdown('<div class="empty-state">No mood entries yet. Add your first entry from Mood Entry.</div>', unsafe_allow_html=True)


for day in sorted_days:
    day_label = day.strftime("%A, %d %B")

    # Sort entries newest → oldest
    day_entries = sorted(grouped[day], key=lambda x: x[0], reverse=True)
    entry_count = len(day_entries)

    st.markdown(
        f"""
        <div class="day-header">
            <h2 class="day-title">{day_label}</h2>
            <span class="count-pill">{entry_count} {'entry' if entry_count == 1 else 'entries'}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Two columns use desktop width better while preserving single-column flow on mobile.
    left_col, right_col = st.columns(2, gap="medium")

    for idx, (ts, e) in enumerate(day_entries):
        mood = e["mood_score"]
        mood_label, mood_bg = mood_meta(mood)
        notes = html.escape(e.get("notes") or "")
        activity_ids = e.get("activity_ids", [])

        chips_html = ""
        if activity_ids:
            chips_html = "".join(
                (
                    f"<span class='chip'><span class='chip-dot'>•</span>{html.escape(activity_lookup.get(aid, f'Unknown ({aid})'))}</span>"
                )
                for aid in activity_ids
            )
        else:
            chips_html = "<span class='empty-note'>No activities logged</span>"

        note_html = notes if notes else "<span class='empty-note'>No notes</span>"

        card_html = f"""
        <div class="entry-card">
            <div class="entry-top">
                <span class="time-tag">{ts.strftime("%H:%M")}</span>
                <span class="mood-pill" style="background:{mood_bg};">Mood {mood} · {mood_label}</span>
            </div>
            <div class="entry-notes">{note_html}</div>
            <div class="chip-wrap">{chips_html}</div>
        </div>
        """

        if idx % 2 == 0:
            with left_col:
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            with right_col:
                st.markdown(card_html, unsafe_allow_html=True)
