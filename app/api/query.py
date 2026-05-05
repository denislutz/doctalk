import asyncio
import logging
import time

from doctalk_shared.models import QueryRequest, QueryResponse, RetrievedChunk, SourceChunk
from fastapi import APIRouter, HTTPException, Request
from langchain_core.language_models import BaseChatModel

from app.retrieval.chain import generate_answer
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
            format=chunk.format,
            page_number=chunk.page,
            section_header=chunk.section_header,
            content_snippet=chunk.content[:500],
            relevance_score=chunk.score,
        )
        for chunk in chunks
    ]


@router.post("")
async def query(request: Request, body: QueryRequest) -> QueryResponse:
    topic = _validate_topics(body.topics)

    vector_db: VectorDB = request.app.state.vector_db_client
    if not vector_db.is_present_collection(topic):
        raise HTTPException(status_code=404, detail=f"Collection '{topic}' not found")

    retrieval_start = time.perf_counter()
    dense_chunks, sparse_chunks = await asyncio.gather(
        search_collection_dense(
            question=body.question,
            collection=topic,
            embedder=request.app.state.embedder,
            vector_db=vector_db,
        ),
        search_collection_sparse(
            question=body.question,
            collection=topic,
            embedder=request.app.state.embedder,
            vector_db=vector_db,
        ),
    )
    # now merge the results using RRF
    fused_chunks = reciprocal_rank_fusion(dense_results=dense_chunks, sparse_results=sparse_chunks)

    ranked_chunks = request.app.state.reranker.rerank(body.question, fused_chunks, top_k=body.top_k)

    unranked_format = [
        {"content": chunk.content[:100], "source": chunk.source_name, "score": chunk.score}
        for chunk in fused_chunks
    ]

    ranked_format = [
        {"content": chunk.content[:100], "source": chunk.source_name, "score": chunk.score}
        for chunk in ranked_chunks
    ]
    logger.debug(f"Unranked chunks: {unranked_format} for {body.question}")
    logger.debug(f"Reranked chunks: {ranked_format} for {body.question}")
    retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

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
