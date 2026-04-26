import os
import streamlit as st
import requests
import datetime
import html
import json
import io
import csv
from zoneinfo import ZoneInfo

API_BASE = os.getenv("API_BASE", "http://backend:8000")

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
    border: 1px solid #c8d9ef;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 700;
    padding: 0.42rem 0.9rem;
    white-space: nowrap;
}

.sleep-pill {
    color: #234766;
    background: #d8efe4;
    border: 1px solid #b8ddcb;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 700;
    padding: 0.42rem 0.9rem;
    white-space: nowrap;
}

.day-header-right {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
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
    background: #e6eef7;
    border: 1px solid #c8d7ea;
    border-radius: 12px;
    padding: 0.28rem 0.62rem;
    font-size: 0.83rem;
}

.mood-pill {
    border-radius: 999px;
    padding: 0.34rem 0.82rem;
    font-size: 0.88rem;
    font-weight: 700;
    color: #20394f;
    white-space: nowrap;
    border: 1px solid rgba(33, 71, 101, 0.16);
}

.mood-pill-1 { background: #b8f0cf; }
.mood-pill-2 { background: #d9efb3; }
.mood-pill-3 { background: #fde58a; }
.mood-pill-4 { background: #f7c597; }
.mood-pill-5 { background: #f5a6a6; }
.mood-pill-none { background: #dfe7f2; }

.mood-marker {
    display: none;
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
    gap: 0.28rem;
    background: var(--chip-bg);
    color: var(--chip-text);
    border: 1px solid #b8cde7;
    border-radius: 999px;
    padding: 0.2rem 0.58rem;
    font-size: 0.82rem;
    font-weight: 600;
}

.chip-dot {
    font-size: 0.74rem;
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

    .day-header-right {
        justify-content: flex-start;
    }

    /* Force stacked layout only for entry-row columns on small screens. */
    section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stVerticalBlockBorderWrapper"]) {
        flex-wrap: wrap !important;
    }

    section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(div[data-testid="stVerticalBlockBorderWrapper"]) > div[data-testid="column"] {
        min-width: 100% !important;
        flex: 1 1 100% !important;
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
    margin-top: 0.85rem;
    color: var(--text-main);
    line-height: 1.4;
    font-size: 1.06rem;
    min-height: 1.1rem;
}

.entry-row-chips {
    margin-top: 0.62rem;
    margin-bottom: 0.16rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
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
    border: 1px solid #cbdcee !important;
    border-radius: 18px !important;
    background: #eef5fb !important;
    box-shadow: none !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin-bottom: 1rem !important;
}

/* Remove Streamlit's internal block padding/gap — we control it */
section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
    padding: 16px 18px 14px !important;
    gap: 2px !important;
}

/* Mood-tinted card backgrounds to match the soft reference look. */
section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.mood-marker-1) {
    background: #dcefe5 !important;
    border-color: #bdddcf !important;
}

section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.mood-marker-2) {
    background: #ebe8d6 !important;
    border-color: #ddd7bb !important;
}

section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.mood-marker-3) {
    background: #ead9d0 !important;
    border-color: #dcc4b7 !important;
}

section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.mood-marker-4) {
    background: #ecd6cb !important;
    border-color: #dbbfaf !important;
}

section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.mood-marker-5) {
    background: #efd1d1 !important;
    border-color: #deb6b6 !important;
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
        border-radius: 16px !important;
        box-shadow: none !important;
        margin-bottom: 0.88rem !important;
    }

    .entry-row-chips {
        margin-top: 0.5rem;
        margin-bottom: 0.16rem;
        gap: 0.24rem;
    }

    .chip {
        padding: 0.12rem 0.48rem;
        font-size: 0.74rem;
    }

    .chip-dot {
        font-size: 0.68rem;
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
    if score is None:
        return ("No rating", "#dfe7f2")
    return MOOD_META.get(score, (f"{score}", "#d1d5db"))


def mood_css_class(score):
    if score in {1, 2, 3, 4, 5}:
        return str(score)
    return "none"


if "open_entry_menu_id" not in st.session_state:
    st.session_state["open_entry_menu_id"] = None
def clear_mood_cache():
    load_entries.clear()
    load_categories.clear()
    load_activities.clear()
    load_sleep_range.clear()


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
        raw_score = row.get("mood_score")
        if raw_score in (None, "", "null"):
            score = None
        else:
            score = int(raw_score)
            if score < 1 or score > 5:
                raise ValueError("mood_score must be between 1 and 5, or empty")

        normalized.append(
            {
                "mood_score": score,
                "notes": row.get("notes") or row.get("note") or None,
                "timestamp": parse_timestamp(row.get("timestamp")),
                "activity_ids": parse_activity_ids(row.get("activity_ids")),
            }
        )

    return normalized


def entry_signature(row):
    raw_notes = row.get("notes")
    normalized_notes = (raw_notes or "").strip()
    timestamp_value = row.get("timestamp")
    if isinstance(timestamp_value, datetime.datetime):
        normalized_ts = timestamp_value.isoformat()
    else:
        normalized_ts = parse_timestamp(timestamp_value)

    return (
        None if row.get("mood_score") is None else int(row.get("mood_score")),
        normalized_notes,
        normalized_ts,
        tuple(sorted(int(aid) for aid in row.get("activity_ids", []))),
    )


def delete_entries(entry_ids):
    deleted = 0
    failed = 0
    for entry_id in entry_ids:
        try:
            resp = requests.delete(f"{API_BASE}/mood/{entry_id}", timeout=4)
            if resp.status_code == 200:
                deleted += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return deleted, failed


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
def load_categories():
    try:
        r = requests.get(f"{API_BASE}/categories/", timeout=3)
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


@st.cache_data(ttl=900, show_spinner=False)
def load_sleep_range(start_date: str, end_date: str):
    try:
        r = requests.get(
            f"{API_BASE}/garmin/sleep/range",
            params={"start_date": start_date, "end_date": end_date},
            timeout=4,
        )
        r.raise_for_status()
        rows = r.json().get("data") or []
        return {
            row.get("date"): row
            for row in rows
            if isinstance(row, dict) and row.get("date")
        }
    except Exception:
        return {}


if "editing_entry_id" not in st.session_state:
    st.session_state["editing_entry_id"] = None
if "delete_confirm_id" not in st.session_state:
    st.session_state["delete_confirm_id"] = None
if "mood_log_flash" not in st.session_state:
    st.session_state["mood_log_flash"] = None
if "bulk_delete_confirm" not in st.session_state:
    st.session_state["bulk_delete_confirm"] = None
if "bulk_clear_rating_confirm" not in st.session_state:
    st.session_state["bulk_clear_rating_confirm"] = False


toolbar_col, refresh_col = st.columns([0.8, 0.2])
with toolbar_col:
    st.caption("Use refresh if entries were added from another device a moment ago.")
with refresh_col:
    if st.button("Refresh", use_container_width=True):
        clear_mood_cache()
        st.rerun()


entries = load_entries()
categories_list = load_categories()
activities_list = load_activities()
activity_lookup = {a["id"]: a["name"] for a in activities_list}
activity_full_lookup = {a["id"]: a for a in activities_list}  # Full activity objects with category_id
category_name_by_id = {c["id"]: c["name"] for c in categories_list}
category_id_by_name = {c["name"]: c["id"] for c in categories_list}
entry_lookup = {e["id"]: e for e in entries}


def matching_entries_for_rating_clear(target_category_ids, include_mixed=False):
    matches = []
    if not target_category_ids:
        return matches

    for entry in entries:
        if entry.get("mood_score") is None:
            continue

        activity_ids = entry.get("activity_ids") or []
        if not activity_ids:
            continue

        entry_category_ids = {
            activity_full_lookup.get(aid, {}).get("category_id")
            for aid in activity_ids
            if activity_full_lookup.get(aid, {}).get("category_id") is not None
        }

        if not entry_category_ids:
            continue

        if include_mixed:
            is_match = bool(entry_category_ids.intersection(target_category_ids))
        else:
            is_match = entry_category_ids.issubset(target_category_ids)

        if is_match:
            matches.append(entry)

    return matches


def clear_ratings(entry_rows):
    updated = 0
    failed = 0
    for row in entry_rows:
        payload = {
            "mood_score": None,
            "notes": row.get("notes"),
            "timestamp": row.get("timestamp"),
            "activity_ids": row.get("activity_ids", []),
        }
        try:
            resp = requests.put(f"{API_BASE}/mood/{row['id']}", json=payload, timeout=4)
            if resp.status_code == 200:
                updated += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return updated, failed


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

    backup_snapshot = {
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "mood_log_tools",
        "entries": export_rows,
        "categories": categories_list,
        "activities": activities_list,
    }
    backup_name = f"mood_log_backup_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    st.download_button(
        "Download Full Backup (JSON)",
        data=json.dumps(backup_snapshot, indent=2),
        file_name=backup_name,
        mime="application/json",
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
            existing_signatures = {entry_signature(entry) for entry in entries}
            seen_import_signatures = set()

            imported = 0
            failed = 0
            skipped_duplicates = 0
            for row in rows_to_import:
                signature = entry_signature(row)
                if signature in existing_signatures or signature in seen_import_signatures:
                    skipped_duplicates += 1
                    continue

                resp = requests.post(f"{API_BASE}/mood/", json=row, timeout=4)
                if resp.status_code in (200, 201):
                    imported += 1
                    existing_signatures.add(signature)
                    seen_import_signatures.add(signature)
                else:
                    failed += 1

            clear_mood_cache()
            st.session_state["mood_log_flash"] = (
                f"Import complete: {imported} imported, {skipped_duplicates} duplicates skipped, {failed} failed."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    st.markdown("---")
    st.subheader("Bulk Delete")
    delete_target_date = st.date_input("Delete entries for date", value=datetime.datetime.now(uk_tz).date())

    if st.button("Delete Selected Day", use_container_width=True):
        st.session_state["bulk_delete_confirm"] = f"day:{delete_target_date.isoformat()}"
        st.rerun()

    if st.button("Delete All Entries", use_container_width=True):
        st.session_state["bulk_delete_confirm"] = "all"
        st.rerun()

    confirm_value = st.session_state.get("bulk_delete_confirm")
    if confirm_value:
        if confirm_value == "all":
            st.warning("Delete all mood log entries? This cannot be undone.")
            target_entry_ids = [entry["id"] for entry in entries]
        else:
            target_date = datetime.date.fromisoformat(confirm_value.split(":", 1)[1])
            st.warning(f"Delete all entries on {target_date.isoformat()}? This cannot be undone.")
            target_entry_ids = [
                entry["id"]
                for entry in entries
                if datetime.datetime.fromisoformat(entry["timestamp"]).astimezone(uk_tz).date() == target_date
            ]

        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Confirm Bulk Delete", use_container_width=True):
                deleted, failed = delete_entries(target_entry_ids)
                clear_mood_cache()
                st.session_state["bulk_delete_confirm"] = None
                st.session_state["mood_log_flash"] = f"Bulk delete complete: {deleted} deleted, {failed} failed."
                st.rerun()
        with cancel_col:
            if st.button("Cancel Bulk Delete", use_container_width=True):
                st.session_state["bulk_delete_confirm"] = None
                st.rerun()

    st.markdown("---")
    st.subheader("Bulk Rating Cleanup")
    cleanup_default_names = [
        name for name in ["Lifestyle", "Before Sleep", "During Sleep"] if name in category_id_by_name
    ]
    cleanup_target_names = st.multiselect(
        "Categories to disassociate rating from",
        options=sorted(category_id_by_name.keys()),
        default=cleanup_default_names,
    )
    cleanup_include_mixed = st.checkbox(
        "Include entries that also contain other categories",
        value=False,
        help="Off = only clear entries where all selected activities are in the chosen categories.",
    )

    cleanup_target_ids = {category_id_by_name[name] for name in cleanup_target_names}
    cleanup_matches = matching_entries_for_rating_clear(cleanup_target_ids, include_mixed=cleanup_include_mixed)
    st.caption(f"Matches with rating to clear: {len(cleanup_matches)}")

    with st.expander("Preview matching entries", expanded=False):
        if cleanup_matches:
            for row in cleanup_matches[:50]:
                ts_local = datetime.datetime.fromisoformat(row["timestamp"]).astimezone(uk_tz)
                row_cat_names = sorted(
                    {
                        category_name_by_id.get(activity_full_lookup.get(aid, {}).get("category_id"), "(uncategorized)")
                        for aid in (row.get("activity_ids") or [])
                    }
                )
                st.write(
                    f"#{row['id']} · {ts_local.strftime('%Y-%m-%d %H:%M')} · Mood {row.get('mood_score')} · "
                    f"Categories: {', '.join(row_cat_names)}"
                )
            if len(cleanup_matches) > 50:
                st.caption(f"Showing first 50 of {len(cleanup_matches)} matches.")
        else:
            st.caption("No matching rated entries found.")

    if st.button("Clear Ratings for Matches", use_container_width=True, disabled=not cleanup_matches):
        st.session_state["bulk_clear_rating_confirm"] = True
        st.rerun()

    if st.session_state.get("bulk_clear_rating_confirm"):
        st.warning(f"Clear rating on {len(cleanup_matches)} matching entries?")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Confirm Clear Ratings", use_container_width=True):
                updated, failed = clear_ratings(cleanup_matches)
                clear_mood_cache()
                st.session_state["bulk_clear_rating_confirm"] = False
                st.session_state["mood_log_flash"] = f"Rating cleanup complete: {updated} updated, {failed} failed."
                st.rerun()
        with cancel_col:
            if st.button("Cancel Clear Ratings", use_container_width=True):
                st.session_state["bulk_clear_rating_confirm"] = False
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

sleep_by_day = {}
if sorted_days:
    min_day = sorted_days[-1].isoformat()
    max_day = sorted_days[0].isoformat()
    sleep_by_day = load_sleep_range(min_day, max_day)

if not sorted_days:
    st.markdown('<div class="empty-state">No mood entries yet. Add your first entry from Mood Entry.</div>', unsafe_allow_html=True)

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
        
        edit_activities = st.multiselect(
            "Activities",
            options=sorted(activity_lookup.keys()),
            default=edit_entry.get("activity_ids", []),
            format_func=lambda aid: activity_lookup.get(aid, f"Unknown ({aid})"),
            key=f"edit_acts_{edit_id}",
        )
        
        # Determine if rating is required for edited activities
        categories_lookup = {cat["id"]: cat for cat in categories_list}
        any_require_rating = False
        rating_labels = set()
        
        for activity_id in edit_activities:
            activity = activity_full_lookup.get(activity_id)
            if activity:
                cat_id = activity.get("category_id")
                cat = categories_lookup.get(cat_id)
                if cat and cat.get("require_rating", 1):
                    any_require_rating = True
                    if cat.get("rating_label"):
                        rating_labels.add(cat.get("rating_label"))
        
        rating_context = "Mood Score" if not rating_labels else list(rating_labels)[0]
        
        if any_require_rating or not edit_activities:
            edit_score = st.radio(
                rating_context,
                options=[1, 2, 3, 4, 5],
                horizontal=True,
                key=f"edit_score_{edit_id}",
                index=max(0, min(4, int(edit_entry.get("mood_score", 3)) - 1)) if edit_entry.get("mood_score") else 2,
            )
        else:
            st.caption("Rating not required for selected activities.")
            edit_score = None
        
        edit_notes = st.text_area("Notes", value=edit_entry.get("notes") or "", key=f"edit_notes_{edit_id}")

        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button("Save Changes", key=f"save_edit_{edit_id}", use_container_width=True):
                new_ts = datetime.datetime.combine(edit_date, edit_time, tzinfo=uk_tz).isoformat()
                payload = {
                    "mood_score": int(edit_score) if edit_score is not None else None,
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
            if st.button("Cancel", key=f"cancel_edit_{edit_id}", use_container_width=True):
                st.session_state["editing_entry_id"] = None
                st.rerun()


for day in sorted_days:
    day_label = day.strftime("%A, %d %B")

    # Sort entries newest → oldest
    day_entries = sorted(grouped[day], key=lambda x: x[0], reverse=True)
    entry_count = len(day_entries)
    sleep_row = sleep_by_day.get(day.isoformat())
    sleep_text = ""
    if sleep_row and sleep_row.get("total_sleep_minutes") is not None:
        total_minutes = int(sleep_row.get("total_sleep_minutes") or 0)
        sleep_hours = total_minutes // 60
        sleep_minutes = total_minutes % 60
        sleep_score = sleep_row.get("sleep_score")
        score_text = f" · {sleep_score}/100" if sleep_score is not None else ""
        sleep_text = f"<span class='sleep-pill'>Sleep {sleep_hours}h {sleep_minutes:02d}m{score_text}</span>"

    header_left, header_right = st.columns([0.62, 0.38], vertical_alignment="center")
    with header_left:
        st.markdown(f"<div class='day-header'><h2 class='day-title'>{day_label}</h2></div>", unsafe_allow_html=True)
    with header_right:
        st.markdown(
            f"""
            <div class="day-header-right">
                {sleep_text}
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
        mood_class = mood_css_class(mood)
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
                st.markdown(f"<div class='mood-marker mood-marker-{mood_class}'></div>", unsafe_allow_html=True)
                header_left, header_mid, header_right = st.columns([0.2, 0.66, 0.14], vertical_alignment="center")
                with header_left:
                    st.markdown(f"<span class='time-tag'>{ts.strftime('%H:%M')}</span>", unsafe_allow_html=True)
                with header_mid:
                    st.markdown(
                        f"<div style='text-align:right;'><span class='mood-pill mood-pill-{mood_class}'>{mood_label if mood is None else f'Mood {mood} · {mood_label}'}</span></div>",
                        unsafe_allow_html=True,
                    )
                with header_right:
                    render_entry_actions(e["id"])

                st.markdown(f"<div class='entry-row-note'>{note_html}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='entry-row-chips'>{chips_html}</div>", unsafe_allow_html=True)
