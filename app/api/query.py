import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from doctalk_shared.models import QueryRequest, QueryResponse, RetrievedChunk, SourceChunk
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.language_models import BaseChatModel

from app.retrieval.chain import generate_answer, stream_answer
from app.retrieval.search_service import (
    reciprocal_rank_fusion,
    search_collection_dense,
    search_collection_sparse,
)
from app.storage.vector_db_client import VectorDB

router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger(__name__)


def _validate_topics(topics: list[str] | None) -> str:
    if not topics or not topics[0].strip() or len(topics) > 1:
        raise HTTPException(status_code=400, detail="Topic is invalid.")
    return topics[0]


def _to_source_chunks(chunks: list[RetrievedChunk]) -> list[SourceChunk]:
    return [
        SourceChunk(
            source_name=chunk.source_name,
            format=chunk.format,
            page_number=chunk.page,
            section_header=chunk.section_header,
            content_snippet=chunk.content[:500],
            relevance_score=chunk.score,
        )
        for chunk in chunks
    ]


async def _retrieve_and_rank(
    question: str,
    topic: str,
    top_k: int,
    request: Request,
) -> tuple[list[RetrievedChunk], float]:
    vector_db: VectorDB = request.app.state.vector_db_client
    start = time.perf_counter()
    dense_chunks, sparse_chunks = await asyncio.gather(
        search_collection_dense(
            question=question,
            collection=topic,
            embedder=request.app.state.embedder,
            vector_db=vector_db,
        ),
        search_collection_sparse(
            question=question,
            collection=topic,
            embedder=request.app.state.embedder,
            vector_db=vector_db,
        ),
    )
    fused_chunks = reciprocal_rank_fusion(dense_results=dense_chunks, sparse_results=sparse_chunks)
    ranked_chunks = request.app.state.reranker.rerank(question, fused_chunks, top_k=top_k)
    retrieval_ms = (time.perf_counter() - start) * 1000
    return ranked_chunks, retrieval_ms


@router.post("")
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    topic = _validate_topics(body.topics)

    vector_db: VectorDB = request.app.state.vector_db_client
    if not vector_db.is_present_collection(topic):
        raise HTTPException(status_code=404, detail=f"Collection '{topic}' not found")

    ranked_chunks, retrieval_ms = await _retrieve_and_rank(body.question, topic, body.top_k, request)

    logger.debug(
        "Reranked chunks: %s for %s",
        [{"content": c.content[:100], "source": c.source_name, "score": c.score} for c in ranked_chunks],
        body.question,
    )

    generation_start = time.perf_counter()
    llm: BaseChatModel = request.app.state.langchain_llm
    answer = await generate_answer(body.question, ranked_chunks, llm, history=body.history)
    generation_ms = (time.perf_counter() - generation_start) * 1000

    return QueryResponse(
        answer=answer,
        sources=_to_source_chunks(ranked_chunks),
        tokens_used=0,
        retrieval_time_ms=retrieval_ms,
        generation_time_ms=generation_ms,
    )


@router.post("/stream")
async def query_stream(request: Request, body: QueryRequest) -> StreamingResponse:
    topic = _validate_topics(body.topics)

    vector_db: VectorDB = request.app.state.vector_db_client
    if not vector_db.is_present_collection(topic):
        raise HTTPException(status_code=404, detail=f"Collection '{topic}' not found")

    ranked_chunks, _ = await _retrieve_and_rank(body.question, topic, body.top_k, request)
    source_chunks = _to_source_chunks(ranked_chunks)
    llm: BaseChatModel = request.app.state.langchain_llm

    async def generate() -> AsyncIterator[str]:
        async for token in stream_answer(body.question, ranked_chunks, llm, history=body.history):
            yield f"data: {token}\n\n"
        yield f"data: {json.dumps({'sources': [s.model_dump() for s in source_chunks]})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
