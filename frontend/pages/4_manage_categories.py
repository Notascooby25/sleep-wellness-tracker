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

        col1, col2 = st.columns(2)

        # Rename
        with col1:
            new_name = st.text_input(f"Rename {c['name']}", key=f"rename_{c['id']}")
            if st.button(f"Save {c['id']}", key=f"save_{c['id']}"):
                if new_name.strip():
                    resp = put_json(f"/categories/{c['id']}", {"name": new_name})
                    if resp and resp.ok:
                        st.success("Updated.")
                        st.rerun()
                    else:
                        st.error("Failed to update.")

        # Delete
        with col2:
            if st.button(f"Delete {c['id']}", key=f"delete_{c['id']}"):
                resp = delete(f"/categories/{c['id']}")
                if resp and resp.ok:
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error("Failed to delete.")
