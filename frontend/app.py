import os

import httpx
import streamlit as st
from doctalk_shared.models import CollectionInfo, QueryResponse

API_URL = os.getenv("API_URL", "http://localhost:8000")

http_client = httpx.Client(timeout=120.0)


st.set_page_config(page_title="DocTalk", page_icon="📄", layout="wide")
st.title("DocTalk")
st.caption("Self-hosted RAG — talk to your data!")

# --- Health check ---
try:
    r = http_client.get(f"{API_URL}/health", timeout=10)
    backend_ready = r.status_code == 200
except (httpx.ConnectError, httpx.ReadTimeout):
    backend_ready = False

# --- Sidebar: topic selector ---
with st.sidebar:
    if backend_ready:
        st.success("Systems ready")
    else:
        st.error("Systems not ready")

    st.header("Current Topic")
    collections = []
    try:
        response = http_client.get(f"{API_URL}/collections")
        if response.status_code == 200:
            collections_full = [CollectionInfo.model_validate(c) for c in response.json()]
            collections = [c.name for c in collections_full]
    except (httpx.ConnectError, httpx.ReadTimeout):
        pass
    if len(collections) == 0:
        st.info("Upload a document first")
    selected = st.selectbox("Existing topics", options=collections or ["Sample Topic"])


# --- Tabs ---
upload_tab, query_tab, topics_tab = st.tabs(["Upload", "Query", "Topics"])


# --- Upload tab ---
with upload_tab:
    st.subheader("Upload a document")

    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
    new_topic = st.text_input(
        f"Name your new topic for the files to be associated with, or leave blank to use the current topic '{selected}'."
    )
    source_name = st.text_input("Original source name (optional)", value="")
    topic = new_topic.strip() if new_topic.strip() else selected

    if st.button("Upload", disabled=uploaded_file is None or not topic):
        assert uploaded_file is not None
        response = http_client.post(
            f"{API_URL}/upload/{topic}",
            files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
            data={"source_name": source_name},
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
        question = st.text_input(
            "Your question, select the right topic before...", value="Staatenlos, was bedeutet das?"
        )
    with k_col:
        top_k = st.slider("Number of sources", min_value=1, max_value=5, value=5)

    if st.button("Ask", disabled=len(question.strip()) < 10):
        with st.spinner("Thinking..."):
            response = http_client.post(
                f"{API_URL}/query",
                json={"question": question, "topics": [topic], "top_k": top_k},
            )
        if response.status_code == 200:
            data = QueryResponse.model_validate(response.json())
            st.markdown(data.answer)
            for source in data.sources:
                with st.expander(
                    f"{source.source_name} · page {source.page_number} · score {source.relevance_score:.3f}"
                ):
                    st.caption(source.content_snippet)
            st.caption(
                f"Retrieval {data.retrieval_time_ms:.0f}ms · Generation {data.generation_time_ms:.0f}ms"
            )
        else:
            error_detail = response.json().get("detail", "Query failed")
            st.toast(error_detail, icon="❌")

with topics_tab:
    st.subheader("Topics")
    response = http_client.get(f"{API_URL}/collections")
    if response.status_code == 200:
        topic_list = [CollectionInfo.model_validate(t) for t in response.json()]
        for col_info in topic_list:
            name_col, desc_col, action_col = st.columns([0.2, 0.4, 0.2])
            name_col.write(col_info.name)
            desc_col.write(f"Size: {col_info.size} chunks")
            if action_col.button("Delete", key=f"delete-{col_info.name}"):
                r = http_client.delete(f"{API_URL}/collections/{col_info.name}")
                if r.status_code == 200:
                    st.toast(f"Deleted {col_info.name}")
                    st.rerun()
                else:
                    st.toast(f"Failed to delete {col_info.name}", icon="❌")
    else:
        st.toast("Failed to get collections", icon="❌")
