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
st.title("Manage Activities")

# Load categories + activities
categories = fetch_json("/categories")
activities = fetch_json("/activities")

# -----------------------------
# Category filter
# -----------------------------
st.subheader("Filter by Category")

category_map = {c["name"]: c["id"] for c in categories} if categories else {}
category_names = list(category_map.keys())
category_name_by_id = {c["id"]: c["name"] for c in categories} if categories else {}

selected_category = st.selectbox("Category", ["(all)"] + category_names)

if selected_category == "(all)":
    filtered = activities
else:
    cid = category_map[selected_category]
    filtered = [a for a in activities if a["category_id"] == cid]

# -----------------------------
# Add new activity
# -----------------------------
st.subheader("Add Activity")

new_name = st.text_input("Activity name")
new_cat = st.selectbox("Category for new activity", ["(uncategorized)"] + category_names)

if st.button("Add Activity"):
    if new_name.strip():
        selected_new_category_id = None if new_cat == "(uncategorized)" else category_map[new_cat]
        resp = post_json("/activities/", {
            "name": new_name,
            "category_id": selected_new_category_id
        })
        if resp and resp.ok:
            st.success("Activity added.")
            st.rerun()
        else:
            st.error("Failed to add activity.")
    else:
        st.warning("Name cannot be empty.")

# -----------------------------
# Existing activities
# -----------------------------
st.subheader("Existing Activities")

if not filtered:
    st.info("No activities found.")
else:
    for a in filtered:
        current_category_name = category_name_by_id.get(a.get("category_id"), "(uncategorized)")
        st.markdown(f"### {a['name']} (ID {a['id']})")
        st.caption(f"Current category: {current_category_name}")

        col1, col2 = st.columns(2)

        # Rename
        with col1:
            edited_name = st.text_input(
                f"Name for activity {a['id']}",
                value=a["name"],
                key=f"rename_{a['id']}"
            )

            current_category_id = a.get("category_id")
            category_options = ["(uncategorized)"] + category_names
            if current_category_id is None:
                default_category_index = 0
            else:
                current_category = category_name_by_id.get(current_category_id)
                default_category_index = category_options.index(current_category) if current_category in category_options else 0

            edited_category_name = st.selectbox(
                f"Category for activity {a['id']}",
                category_options,
                index=default_category_index,
                key=f"category_{a['id']}"
            )

            if st.button(f"Save {a['id']}", key=f"save_{a['id']}"):
                if edited_name.strip():
                    edited_category_id = None if edited_category_name == "(uncategorized)" else category_map[edited_category_name]
                    resp = put_json(
                        f"/activities/{a['id']}",
                        {"name": edited_name.strip(), "category_id": edited_category_id}
                    )
                    if resp and resp.ok:
                        st.success("Updated.")
                        st.rerun()
                    else:
                        st.error("Failed to update.")
                else:
                    st.warning("Name cannot be empty.")

        # Delete
        with col2:
            if st.button(f"Delete {a['id']}", key=f"delete_{a['id']}"):
                resp = delete(f"/activities/{a['id']}")
                if resp and resp.ok:
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error("Failed to delete.")
