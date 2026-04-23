import logging
import time
from typing import Any

from doctalk_shared.models import ChatMessage, QueryRequest, QueryResponse, SourceChunk
from fastapi import APIRouter, HTTPException, Request

from app.ingestion.embedder import Embedder
from app.llm.ollama_client import OllamaClient
from app.storage.vector_db_client import VectorDB

router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a helpful assistant that answers questions based on the provided context.
You must always cite your sources using the format [Source: filename, page number].
If you cannot find an answer in the context, say "I couldn't find this information in the provided documents."
"""
USER_PROMPT = """
Context:
{formatted_chunks}

Question:
{user_question}
"""

MINIMAL_SCORE = 0.3


def _validate_topics(topics: list[str] | None) -> str:
    if not topics or not topics[0].strip() or len(topics) > 1:
        raise HTTPException(status_code=400, detail="Topic is invalid.")

    return topics[0]


def _embed_question(request: Request, question: str) -> list[float]:
    embedder: Embedder = request.app.state.embedder
    embeddings = embedder.embed([question])
    return embeddings[0]


def _retrieve(
    *, request: Request, topic: str, question_embeddings: list[float], top_k: int
) -> list[tuple[dict[str, Any], float]]:
    vector_db: VectorDB = request.app.state.vector_db_client
    if not vector_db.is_present_collection(topic):
        raise HTTPException(
            status_code=404,
            detail=f"Topic '{topic}' not found, pls create a topic first and upload some docs to start asking questions.",
        )
    return vector_db.search(collection=topic, vector=question_embeddings, top_k=top_k)


def _build_prompt(question: str, hits: list[tuple[dict[str, Any], float]]) -> tuple[str, str]:
    formatted_chunks = ""

    for hit in hits:
        payload, score = hit
        if score < MINIMAL_SCORE:
            continue
        source_name = payload.get("source_name", "")
        page = payload.get("page", "")
        content = payload.get("content", "")
        chunk = f"Source: {source_name}, page: {page}\n{content}\n\n"
        formatted_chunks += chunk
    user_message = USER_PROMPT.format(formatted_chunks=formatted_chunks, user_question=question)
    logger.debug(f"Resulting Prompt | System: {SYSTEM_PROMPT}\n User: {user_message}")
    return SYSTEM_PROMPT.strip(), user_message.strip()


async def _generate_anwser(
    *, request: Request, system_content: str, user_content: str, history: list[ChatMessage]
) -> str:
    chat_model: OllamaClient = request.app.state.chat_model
    return await chat_model.generate(
        system_content=system_content, user_content=user_content, history=history
    )


def _to_source_chunks(hits: list[tuple[dict[str, Any], float]]) -> list[SourceChunk]:
    source_chunks = []
    for payload, score in hits:
        ch = SourceChunk(
            source_name=payload["source_name"],
            format=payload.get("format", "pdf"),
            page_number=payload.get("page"),
            content_snippet=payload["content"][:500],
            relevance_score=score,
        )
        source_chunks.append(ch)
    return source_chunks


@router.post("")
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    topics, question, top_k = body.topics, body.question, body.top_k
    topic = _validate_topics(topics)

    t0 = time.perf_counter()
    # transform the question to embeddings
    question_embeddings = _embed_question(request, question)

    # retrieve the most relevant chunks using the question embeddings
    context_enrichment = _retrieve(
        request=request,
        topic=topic,
        question_embeddings=question_embeddings,
        top_k=top_k,
    )
    retrieval_ms = (time.perf_counter() - t0) * 1000
    system, user = _build_prompt(question, context_enrichment)

    t1 = time.perf_counter()
    answer = await _generate_anwser(
        request=request, system_content=system, user_content=user, history=body.history
    )
    generation_ms = (time.perf_counter() - t1) * 1000

    return QueryResponse(
        answer=answer,
        sources=_to_source_chunks(context_enrichment),
        tokens_used=0,
        retrieval_time_ms=retrieval_ms,
        generation_time_ms=generation_ms,
    )
