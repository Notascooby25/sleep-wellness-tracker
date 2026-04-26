import os
import streamlit as st
import requests
import time
from requests.exceptions import RequestException
from json import JSONDecodeError

API_BASE = os.getenv("API_BASE", "http://backend:8000")

# -----------------------------
# Safe fetch helper
# -----------------------------
def fetch_json(path, retries=5, delay=1.0, timeout=3):
    url = f"{API_BASE}{path}"
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                try:
                    return r.json()
                except JSONDecodeError:
                    st.error("Invalid JSON from backend.")
                    return []
            else:
                st.warning(f"Backend returned {r.status_code}")
                return []
        except RequestException:
            if attempt == retries:
                st.error("Backend unreachable.")
                return []
            time.sleep(delay)

# -----------------------------
# Safe POST/PUT/DELETE helpers
# -----------------------------
def post_json(path, payload):
    try:
        return requests.post(f"{API_BASE}{path}", json=payload)
    except:
        st.error("Failed to reach backend.")
        return None

def put_json(path, payload):
    try:
        return requests.put(f"{API_BASE}{path}", json=payload)
    except:
        st.error("Failed to reach backend.")
        return None

def delete(path):
    try:
        return requests.delete(f"{API_BASE}{path}")
    except:
        st.error("Failed to reach backend.")
        return None

# -----------------------------
# Page UI
# -----------------------------
st.title("Manage Categories")

# Load categories
categories = fetch_json("/categories")

# -----------------------------
# Add new category
# -----------------------------
st.subheader("Add Category")
new_name = st.text_input("New category name")

if st.button("Add Category"):
    if new_name.strip():
        resp = post_json("/categories/", {"name": new_name})
        if resp and resp.ok:
            st.success("Category added.")
            st.rerun()
        else:
            st.error("Failed to add category.")
    else:
        st.warning("Name cannot be empty.")

# -----------------------------
# Existing categories
# -----------------------------
st.subheader("Existing Categories")

if not categories:
    st.info("No categories found.")
else:
    for c in categories:
        st.markdown(f"### {c['name']} (ID {c['id']})")

        with st.expander("Edit Details", expanded=False):
            col1, col2 = st.columns(2)

            # Rename
            with col1:
                new_name = st.text_input(f"Category name", value=c.get("name", ""), key=f"rename_{c['id']}")

            # Rating requirement
            with col2:
                require_rating = st.checkbox(
                    "Require rating?",
                    value=bool(c.get("require_rating", 1)),
                    key=f"require_rating_{c['id']}",
                    help="If disabled, mood entry will show 'Rating not required' for activities in this category."
                )

            # Rating label (context-dependent)
            rating_label = st.text_input(
                "Rating label (optional)",
                value=c.get("rating_label") or "",
                placeholder="e.g., 'Pain/Discomfort Level', 'Prep Quality'",
                key=f"rating_label_{c['id']}",
                help="Shows this label instead of 'Mood Score'. Leave empty to use 'Mood Score'."
            )

            # Save button
            save_col, delete_col = st.columns(2)
            with save_col:
                if st.button(f"Save Changes", key=f"save_{c['id']}", use_container_width=True):
                    if new_name.strip():
                        payload = {
                            "name": new_name.strip(),
                            "require_rating": 1 if require_rating else 0,
                            "rating_label": rating_label.strip() if rating_label.strip() else None,
                        }
                        resp = put_json(f"/categories/{c['id']}", payload)
                        if resp and resp.ok:
                            st.success("Updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update.")
                    else:
                        st.warning("Name cannot be empty.")

            # Delete
            with delete_col:
                if st.button(f"Delete Category", key=f"delete_{c['id']}", use_container_width=True):
                    resp = delete(f"/categories/{c['id']}")
                    if resp and resp.ok:
                        st.success("Deleted.")
                        st.rerun()
                    else:
                        st.error("Failed to delete.")
