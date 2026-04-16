import os

import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "changeme")

st.set_page_config(page_title="DocTalk", page_icon="📄", layout="wide")

st.title("DocTalk")
st.caption("Self-hosted RAG — talk to your documents")

st.info("Frontend coming soon. Backend is running.")

# Verify API connectivity
import httpx

try:
    r = httpx.get(f"{API_URL}/health", timeout=3)
    if r.status_code == 200:
        st.success(f"API connected: {API_URL}")
    else:
        st.error(f"API returned {r.status_code}")
except Exception as e:
    st.error(f"Cannot reach API at {API_URL}: {e}")
