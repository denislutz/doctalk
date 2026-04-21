import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

http_client = httpx.Client(timeout=120.0)


st.set_page_config(page_title="DocTalk", page_icon="📄", layout="wide")
st.title("DocTalk")
st.caption("Self-hosted RAG — talk to your data!")


# --- Sidebar: topic selector ---
with st.sidebar:
    # --- Health check ---
    r = http_client.get(f"{API_URL}/health", timeout=3)
    backend_ready = r.status_code == 200
    if backend_ready:
        st.success("Systems ready")
    else:
        st.error("Systems not ready")

    st.header("Current Topic")
    response = http_client.get(f"{API_URL}/collections")
    collections = []
    if response.status_code == 200:
        collections = response.json()
    if len(collections) == 0:
        st.info("Upload a document first")
    selected = st.selectbox("Existing topic", options=collections or ["Sample Topic"])


# --- Tabs ---
upload_tab, query_tab = st.tabs(["Upload", "Query"])


# --- Upload tab ---
with upload_tab:
    st.subheader("Upload a document")

    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
    new_topic = st.text_input(
        f"Name your new topic for the files to be associated with, or leave blank to use the current topic '{selected}'."
    )
    original_source_name = st.text_input("Original source name (optional)", value="")
    topic = new_topic.strip() if new_topic.strip() else selected

    if st.button("Upload", disabled=uploaded_file is None or not topic):
        assert uploaded_file is not None
        response = http_client.post(
            f"{API_URL}/upload/{topic}",
            files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
            data={"original_source_name": original_source_name},
        )
        if response.status_code == 200:
            st.success(
                f"Uploaded {response.json().get('doc_id')} — {response.json().get('chunk_count')} chunks indexed"
            )
            if topic not in collections:
                st.rerun()
        else:
            st.error(response.json().get("detail", "Upload failed"))

    # Direct context checkbox — no-op in this slice
    st.divider()
    use_direct_context = st.checkbox(
        "Direct context, no RAG (files up to 5 MB)",
        disabled=True,
    )
    st.caption("Coming soon — not wired in this slice.")


# --- Query tab ---
with query_tab:
    st.subheader("Ask a question")
    q_col, k_col = st.columns([0.8, 0.2])
    with q_col:
        question = st.text_input("Your question, select the right topic before...")
    with k_col:
        top_k = st.slider("Number of sources", min_value=1, max_value=5, value=5)

    if st.button("Ask", disabled=len(question.strip()) < 10):
        with st.spinner("Thinking..."):
            response = http_client.post(
                f"{API_URL}/query",
                json={"question": question, "topics": [topic], "top_k": top_k},
            )
        if response.status_code == 200:
            response_data = response.json()
            st.markdown(response_data["answer"])
            sources = response_data["sources"]
            for source in sources:
                with st.expander(
                    f"{source['filename']} · page {source['page_number']} · score {source['relevance_score']:.3f}"
                ):
                    st.caption(source["content_snippet"])
            st.caption(
                f"Retrieval {response_data['retrieval_time_ms']:.0f}ms · Generation {response_data['generation_time_ms']:.0f}ms"
            )
        else:
            st.error("Query failed")
