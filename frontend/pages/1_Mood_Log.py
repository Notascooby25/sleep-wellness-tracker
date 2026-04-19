import streamlit as st
import requests
import datetime
import html
import json
import io
import csv
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

div[data-testid="stPopover"] button:has(div p:only-child) {
    min-height: 1.6rem !important;
    padding: 0 0.46rem !important;
    border-radius: 999px !important;
    border: 1px solid #d8e3f1 !important;
    color: #516b89 !important;
    background: #f4f8fd !important;
    font-size: 0.95rem !important;
    line-height: 1 !important;
}

.entry-row-note {
    margin-top: 0.5rem;
    color: var(--text-main);
    line-height: 1.4;
    font-size: 0.94rem;
    min-height: 1.1rem;
}

.entry-row-chips {
    margin-top: 0.62rem;
    margin-bottom: 0.2rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
}

.entry-row-actions button {
    min-height: 1.5rem !important;
    height: 1.5rem !important;
    padding: 0 0.5rem !important;
    border-radius: 999px !important;
    border: 1px solid #d8e3f1 !important;
    color: #516b89 !important;
    background: #f4f8fd !important;
    font-size: 0.9rem !important;
    line-height: 1 !important;
}

/* Streamlit border container — entry cards in main content only */
section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 2px solid #c2d5ec !important;
    border-radius: 14px !important;
    background: #ffffff !important;
    box-shadow: 0 4px 12px rgba(30, 58, 138, 0.08) !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin-bottom: 0.72rem !important;
}

/* Remove Streamlit's internal block padding/gap — we control it */
section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
    padding: 10px 12px 10px !important;
    gap: 2px !important;
}

/* Remove default paragraph margins that inflate card height */
section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] p {
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.3 !important;
}

/* Compact column spacing inside card header */
section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
    gap: 4px !important;
    padding-bottom: 0 !important;
}

@media (max-width: 860px) {
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 2px solid #a7c2e4 !important;
        border-radius: 14px !important;
        background: #ffffff !important;
        box-shadow: 0 4px 14px rgba(30, 58, 138, 0.12) !important;
        margin-bottom: 0.8rem !important;
    }

    .entry-row-chips {
        margin-bottom: 0.32rem;
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


if "open_entry_menu_id" not in st.session_state:
    st.session_state["open_entry_menu_id"] = None
def clear_mood_cache():
    load_entries.clear()
    load_activities.clear()


def parse_timestamp(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat()

    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp is required")

    ts = value.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"

    datetime.datetime.fromisoformat(ts)
    return ts


def parse_activity_ids(value):
    if value is None:
        return []

    if isinstance(value, list):
        return sorted({int(v) for v in value if str(v).strip()})

    if isinstance(value, str):
        raw = value.replace(";", ",")
        return sorted({int(v.strip()) for v in raw.split(",") if v.strip()})

    raise ValueError("activity_ids must be a list or delimited string")


def normalize_import_rows(rows):
    normalized = []
    for row in rows:
        score = int(row.get("mood_score"))
        if score < 1 or score > 5:
            raise ValueError("mood_score must be between 1 and 5")

        normalized.append(
            {
                "mood_score": score,
                "notes": row.get("notes") or row.get("note") or None,
                "timestamp": parse_timestamp(row.get("timestamp")),
                "activity_ids": parse_activity_ids(row.get("activity_ids")),
            }
        )

    return normalized


def render_entry_actions(entry_id):
    st.markdown('<div class="entry-row-actions">', unsafe_allow_html=True)
    with st.popover("⋯"):
        if st.button("Edit", key=f"menu_edit_{entry_id}", use_container_width=True):
            st.session_state["editing_entry_id"] = entry_id
            st.session_state["delete_confirm_id"] = None
            st.rerun()
        if st.button("Delete", key=f"menu_delete_{entry_id}", use_container_width=True):
            st.session_state["delete_confirm_id"] = entry_id
            st.session_state["editing_entry_id"] = None
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state["delete_confirm_id"] == entry_id:
        st.warning("Delete this entry? This cannot be undone.")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Confirm Delete", key=f"confirm_delete_{entry_id}", use_container_width=True):
                try:
                    resp = requests.delete(f"{API_BASE}/mood/{entry_id}", timeout=4)
                    if resp.status_code == 200:
                        clear_mood_cache()
                        st.session_state["delete_confirm_id"] = None
                        st.session_state["mood_log_flash"] = f"Entry #{entry_id} deleted."
                        st.rerun()
                    else:
                        st.error(f"Delete failed: {resp.status_code} {resp.text}")
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")
        with cancel_col:
            if st.button("Cancel", key=f"cancel_delete_{entry_id}", use_container_width=True):
                st.session_state["delete_confirm_id"] = None
                st.rerun()


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


if "editing_entry_id" not in st.session_state:
    st.session_state["editing_entry_id"] = None
if "delete_confirm_id" not in st.session_state:
    st.session_state["delete_confirm_id"] = None
if "mood_log_flash" not in st.session_state:
    st.session_state["mood_log_flash"] = None


toolbar_col, refresh_col = st.columns([0.8, 0.2])
with toolbar_col:
    st.caption("Use refresh if entries were added from another device a moment ago.")
with refresh_col:
    if st.button("Refresh", use_container_width=True):
        clear_mood_cache()
        st.rerun()


entries = load_entries()
activities_list = load_activities()
activity_lookup = {a["id"]: a["name"] for a in activities_list}
entry_lookup = {e["id"]: e for e in entries}


if st.session_state["mood_log_flash"]:
    st.success(st.session_state["mood_log_flash"])
    st.session_state["mood_log_flash"] = None


with st.sidebar:
    st.subheader("Mood Log Tools")
    export_rows = [
        {
            "mood_score": e.get("mood_score"),
            "notes": e.get("notes"),
            "timestamp": e.get("timestamp"),
            "activity_ids": e.get("activity_ids", []),
        }
        for e in entries
    ]

    export_json = json.dumps(export_rows, indent=2)
    st.download_button(
        "Export JSON",
        data=export_json,
        file_name="mood_log_export.json",
        mime="application/json",
        use_container_width=True,
    )

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["mood_score", "notes", "timestamp", "activity_ids"])
    writer.writeheader()
    for row in export_rows:
        writer.writerow(
            {
                "mood_score": row["mood_score"],
                "notes": row.get("notes") or "",
                "timestamp": row["timestamp"],
                "activity_ids": ";".join(str(aid) for aid in row.get("activity_ids", [])),
            }
        )
    st.download_button(
        "Export CSV",
        data=csv_buffer.getvalue(),
        file_name="mood_log_export.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.markdown("---")
    import_file = st.file_uploader("Import mood log (JSON or CSV)", type=["json", "csv"])
    if st.button("Import Entries", use_container_width=True, disabled=import_file is None):
        try:
            if import_file.name.lower().endswith(".json"):
                payload_obj = json.loads(import_file.getvalue().decode("utf-8"))
                rows = payload_obj.get("entries", []) if isinstance(payload_obj, dict) else payload_obj
                if not isinstance(rows, list):
                    raise ValueError("JSON import must be a list of rows or an object with an entries list")
            else:
                text = import_file.getvalue().decode("utf-8")
                rows = list(csv.DictReader(io.StringIO(text)))

            rows_to_import = normalize_import_rows(rows)

            imported = 0
            failed = 0
            for row in rows_to_import:
                resp = requests.post(f"{API_BASE}/mood/", json=row, timeout=4)
                if resp.status_code in (200, 201):
                    imported += 1
                else:
                    failed += 1

            clear_mood_cache()
            st.session_state["mood_log_flash"] = f"Import complete: {imported} imported, {failed} failed."
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    if st.session_state["editing_entry_id"] is not None:
        edit_id = st.session_state["editing_entry_id"]
        edit_entry = entry_lookup.get(edit_id)
        if edit_entry is None:
            st.session_state["editing_entry_id"] = None
        else:
            parsed_ts = datetime.datetime.fromisoformat(edit_entry["timestamp"]).astimezone(uk_tz)
            st.markdown("---")
            st.subheader(f"Edit Entry #{edit_id}")
            edit_date = st.date_input("Date", value=parsed_ts.date(), key=f"edit_date_{edit_id}")
            edit_time = st.time_input("Time", value=parsed_ts.time(), key=f"edit_time_{edit_id}")
            edit_score = st.radio(
                "Mood",
                options=[1, 2, 3, 4, 5],
                horizontal=True,
                key=f"edit_score_{edit_id}",
                index=max(0, min(4, int(edit_entry.get("mood_score", 3)) - 1)),
            )
            edit_activities = st.multiselect(
                "Activities",
                options=sorted(activity_lookup.keys()),
                default=edit_entry.get("activity_ids", []),
                format_func=lambda aid: activity_lookup.get(aid, f"Unknown ({aid})"),
                key=f"edit_acts_{edit_id}",
            )
            edit_notes = st.text_area("Notes", value=edit_entry.get("notes") or "", key=f"edit_notes_{edit_id}")

            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("Save Changes", use_container_width=True):
                    new_ts = datetime.datetime.combine(edit_date, edit_time, tzinfo=uk_tz).isoformat()
                    payload = {
                        "mood_score": int(edit_score),
                        "notes": edit_notes,
                        "timestamp": new_ts,
                        "activity_ids": sorted(edit_activities),
                    }
                    try:
                        resp = requests.put(f"{API_BASE}/mood/{edit_id}", json=payload, timeout=4)
                        if resp.status_code == 200:
                            clear_mood_cache()
                            st.session_state["editing_entry_id"] = None
                            st.session_state["mood_log_flash"] = f"Entry #{edit_id} updated."
                            st.rerun()
                        else:
                            st.error(f"Update failed: {resp.status_code} {resp.text}")
                    except Exception as exc:
                        st.error(f"Update failed: {exc}")
            with cancel_col:
                if st.button("Cancel", use_container_width=True):
                    st.session_state["editing_entry_id"] = None
                    st.rerun()


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

        target_col = left_col if idx % 2 == 0 else right_col
        with target_col:
            with st.container(border=True):
                header_left, header_mid, header_right = st.columns([0.2, 0.66, 0.14], vertical_alignment="center")
                with header_left:
                    st.markdown(f"<span class='time-tag'>{ts.strftime('%H:%M')}</span>", unsafe_allow_html=True)
                with header_mid:
                    st.markdown(
                        f"<div style='text-align:right;'><span class='mood-pill' style='background:{mood_bg};'>Mood {mood} · {mood_label}</span></div>",
                        unsafe_allow_html=True,
                    )
                with header_right:
                    render_entry_actions(e["id"])

                st.markdown(f"<div class='entry-row-note'>{note_html}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='entry-row-chips'>{chips_html}</div>", unsafe_allow_html=True)
