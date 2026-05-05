import logging
import os
import pathlib
import traceback

import httpx
import streamlit as st
from doctalk_shared.log_setup import setup_logging
from doctalk_shared.models import ChatMessage, CollectionInfo, QueryResponse

API_URL = os.getenv("API_URL", "http://localhost:8000")

setup_logging(
    "frontend.log",
    level=logging.INFO,
    log_dir=pathlib.Path(__file__).resolve().parents[1] / "logs",
)
logger = logging.getLogger(__name__)
logger.info("Frontend started")


def _show_error(message: str, detail: str | None = None) -> None:
    st.error(message)
    if detail:
        with st.expander("Technical details"):
            st.code(detail, language=None)


_is_local = any(h in API_URL for h in ("localhost", "127.0.0.1"))
_startup_timeout = 60.0 if _is_local else 10.0

http_client = httpx.Client(timeout=120.0)


st.set_page_config(page_title="DocTalk", page_icon="📄", layout="wide")
st.title("DocTalk")
st.caption("Self-hosted RAG — talk to your data!")

# --- Health check ---
health_data: dict[str, str] = {}
try:
    r = http_client.get(f"{API_URL}/health", timeout=_startup_timeout)
    if r.status_code == 200:
        health_data = r.json()
except (httpx.ConnectError, httpx.ReadTimeout) as e:
    logger.error("Health check failed: %s", e)

backend_ready = health_data.get("status") == "ok"

# --- Fetch collections once ---
collections_full: list[CollectionInfo] = []
try:
    response = http_client.get(f"{API_URL}/collections")
    if response.status_code == 200:
        collections_full = [CollectionInfo.model_validate(c) for c in response.json()]
except (httpx.ConnectError, httpx.ReadTimeout):
    pass

collection_names = [c.name for c in collections_full]

# --- Sidebar ---
with st.sidebar:
    if backend_ready:
        st.success("Systems ready")
    elif health_data.get("status") == "degraded":
        degraded_keys = [k for k, v in health_data.items() if v.startswith("error:")]
        st.warning(f"Degraded: {', '.join(degraded_keys)} unavailable")
    else:
        st.error("Systems not ready")

    with st.expander("🧪 Error testing"):
        if st.button("Throw backend error", use_container_width=True):
            try:
                r = http_client.get(f"{API_URL}/debug/error")
                _show_error("Backend error triggered.", r.text)
            except Exception as e:
                _show_error("Could not reach backend.", str(e))
        if st.button("Throw frontend error", use_container_width=True):
            try:
                raise RuntimeError("Intentional test error from the frontend")
            except Exception as e:
                logger.exception("Unhandled frontend exception: %s", e)
                _show_error("Frontend error triggered.", traceback.format_exc())

    st.header("Topic")
    if not collection_names:
        st.info("Upload a document first")
    selected = st.selectbox("Select topic", options=collection_names or ["AllTopics-Default"])

    # --- Documents in selected topic ---
    selected_collection = next((c for c in collections_full if c.name == selected), None)
    if selected_collection and selected_collection.documents:
        st.divider()
        st.subheader("Documents")
        for doc in selected_collection.documents:
            st.markdown(f"- {doc.source_name}")

    # --- Delete topic at the bottom ---
    if selected_collection:
        st.divider()
        if st.button("Delete topic", type="secondary", use_container_width=True):
            r = http_client.delete(f"{API_URL}/collections/{selected_collection.name}")
            if r.status_code == 200:
                st.toast(f"Deleted {selected_collection.name}")
                st.rerun()
            else:
                _show_error(
                    f"Could not delete topic '{selected_collection.name}'.",
                    r.text,
                )

# resolve topic for upload tab
topic = selected if selected else ""

# --- Tabs ---
query_tab, upload_tab = st.tabs(["Query", "Upload"])
with query_tab:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

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
            logger.error("Query failed: %s", response.text)
            _show_error("Something went wrong while answering your question.", response.text)


with upload_tab:
    st.subheader("Upload a document")

    uploaded_files = st.file_uploader(
        "Choose files", type=["pdf", "docx", "txt", "md", "epub"], accept_multiple_files=True
    )
    new_topic = st.text_input(f"New topic name, or leave blank to use '{selected}'.")
    source_name = st.text_input("Original source name (optional, applies to all files)", value="")
    topic = new_topic.strip() if new_topic.strip() else selected

    if st.button("Upload", disabled=not uploaded_files or not topic):
        failed = []
        for uploaded_file in uploaded_files:
            try:
                response = http_client.post(
                    f"{API_URL}/upload/{topic}",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            "application/octet-stream",
                        )
                    },
                    data={"source_name": source_name},
                )
                if response.status_code == 200:
                    body = response.json()
                    if body.get("skipped"):
                        st.toast(f"{uploaded_file.name}: already indexed in this topic", icon="⚠️")
                        failed.append(uploaded_file.name)
                    else:
                        st.success(
                            f"{uploaded_file.name} — {body.get('chunk_count')} chunks indexed"
                        )
                else:
                    failed.append(uploaded_file.name)
                    _show_error(
                        f"Failed to upload '{uploaded_file.name}'.",
                        response.text,
                    )
            except Exception as e:
                failed.append(uploaded_file.name)
                _show_error(f"Failed to upload '{uploaded_file.name}'.", str(e))
        if not failed:
            st.rerun()

    # Direct context checkbox — no-op in this slice
    st.divider()
    st.checkbox("Direct context, no RAG (files up to 5 MB)", disabled=True)
    st.caption("Coming soon — not wired in this slice.")
