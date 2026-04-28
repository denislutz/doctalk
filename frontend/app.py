import logging
import os

import httpx
import streamlit as st
from doctalk_shared.models import ChatMessage, CollectionInfo, QueryResponse

API_URL = os.getenv("API_URL", "http://localhost:8000")

logger = logging.getLogger(__name__)

http_client = httpx.Client(timeout=120.0)


st.set_page_config(page_title="DocTalk", page_icon="📄", layout="wide")
st.title("DocTalk")
st.caption("Self-hosted RAG — talk to your data!")

# --- Health check ---
health_data: dict[str, str] = {}
try:
    r = http_client.get(f"{API_URL}/health", timeout=10)
    if r.status_code == 200:
        health_data = r.json()
except (httpx.ConnectError, httpx.ReadTimeout):
    pass

backend_ready = health_data.get("status") == "ok"

# --- Sidebar: topic selector ---
with st.sidebar:
    if backend_ready:
        st.success("Systems ready")
    elif health_data.get("status") == "degraded":
        failed = [k for k, v in health_data.items() if v.startswith("error:")]
        st.warning(f"Degraded: {', '.join(failed)} unavailable")
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
    selected = st.selectbox("Existing topics", options=collections or ["AllTopics-Default"])


# --- Tabs ---
upload_tab, query_tab, topics_tab = st.tabs(["Upload", "Query", "Topics"])


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
            st.rerun()
        else:
            reason = response.json().get("detail", "Unknown error")
            st.toast(f"Upload failed: {reason}", icon="❌")

    # Direct context checkbox — no-op in this slice
    st.divider()
    use_direct_context = st.checkbox(
        "Direct context, no RAG (files up to 5 MB)",
        disabled=True,
    )
    st.caption("Coming soon — not wired in this slice.")

with query_tab:
    # Reset it when the topic changes so history doesn't bleed across collections.
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Render prior turns here before the input so the user sees the thread.
    for chat_msg in st.session_state["chat_history"]:
        with st.chat_message(chat_msg.role):
            st.markdown(chat_msg.content)

    q_col, btn_col = st.columns([0.8, 0.2], vertical_alignment="bottom")
    with q_col:
        question = st.text_input("Your question, select the right topic before...")
    with btn_col:
        ask = st.button("Ask 🚀", type="primary", disabled=len(question.strip()) < 10)

    if ask:
        NUMBER_OF_SOURCES = 5
        with st.spinner("Thinking..."):
            response = http_client.post(
                f"{API_URL}/query",
                json={
                    "question": question,
                    "topics": [topic],
                    "top_k": NUMBER_OF_SOURCES,
                    "history": [m.model_dump() for m in st.session_state["chat_history"]],
                },
            )
        if response.status_code == 200:
            data = QueryResponse.model_validate(response.json())

            # Append the new turn so follow-ups include it. Cap length if context gets too long.
            st.session_state["chat_history"].append(ChatMessage(role="user", content=question))
            st.session_state["chat_history"].append(
                ChatMessage(role="assistant", content=data.answer)
            )

            st.markdown(data.answer)
            for source in data.sources:
                with st.expander(
                    f"{source.source_name} · page {source.page_number} · score {source.relevance_score:.3f}"
                ):
                    st.caption(source.content_snippet)
            st.caption(
                f"Retrieval {data.retrieval_time_ms:.0f}ms · Generation {data.generation_time_ms:.0f}ms"
            )
            st.rerun()
        else:
            error_detail = response.json().get("detail", "Query failed")
            st.toast(error_detail, icon="❌")

    # Add a "Clear conversation" button here.

with topics_tab:
    st.subheader("Topics")
    response = http_client.get(f"{API_URL}/collections")
    if response.status_code == 200:
        topic_infos = [CollectionInfo.model_validate(t) for t in response.json()]
        name_col, desc_col, size_col, action_col = st.columns([0.1, 0.5, 0.1, 0.2])
        # cols labels
        name_col.write("Name")
        desc_col.write("Documents")
        size_col.write("Docs count")
        action_col.write("Action")
        for collection_info in topic_infos:
            name_col.write(collection_info.name)
            doc_names = "  \n".join([doc.source_name for doc in collection_info.documents])
            logger.debug(f"Document names for {collection_info.name}: {doc_names}")
            desc_col.markdown(doc_names)
            size_col.write(collection_info.doc_count)
            if action_col.button("Delete", key=f"delete-{collection_info.name}"):
                r = http_client.delete(f"{API_URL}/collections/{collection_info.name}")
                if r.status_code == 200:
                    st.toast(f"Deleted {collection_info.name}")
                    st.rerun()
                else:
                    st.toast(f"Failed to delete {collection_info.name}", icon="❌")
    else:
        st.toast("Failed to get collections", icon="❌")
