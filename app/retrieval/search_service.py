from doctalk_shared.models import RetrievedChunk

from app.config import settings
from app.ingestion.embedder import Embedder
from app.storage.vector_db_client import VectorDB


async def search_collection_sparse(
    *,
    question: str,
    collection: str,
    vector_db: VectorDB,
    embedder: Embedder,
    top_k: int = settings.search_top_k,
) -> list[RetrievedChunk]:
    # Sparse keyword search using BM25 via Qdrant's built-in sparse vector support.
    # Requires the collection to have been indexed with a sparse vector field at ingest time.
    # Query is tokenised into a sparse vector (term → weight map) and searched against
    # the stored sparse vectors. Returns the same RetrievedChunk shape as dense search
    # so results can be fed directly into reciprocal_rank_fusion().
    vector = embedder.embed_sparse([question])[0]
    hits = vector_db.search_sparse(collection=collection, sparse_vector=vector, top_k=top_k)
    return [
        RetrievedChunk(
            content=str(payload.get("content", "")),
            source_name=str(payload.get("source_name", "")),
            format=str(payload.get("format", "")),
            page=int(payload["page"]) if payload.get("page") is not None else None,  # type: ignore[call-overload]
            section_header=str(payload["section_header"])
            if payload.get("section_header")
            else None,
            score=score,
        )
        for payload, score in hits
    ]


def reciprocal_rank_fusion(
    *,
    dense_results: list[RetrievedChunk],
    sparse_results: list[RetrievedChunk],
    top_k: int = settings.search_top_k,
    k: int = 60,
) -> list[RetrievedChunk]:
    rrf_scores: dict[str, float] = {}
    chunk_by_key: dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(dense_results):
        key = f"{chunk.source_name}::{chunk.content[:64]}"
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        chunk_by_key[key] = chunk

    for rank, chunk in enumerate(sparse_results):
        key = f"{chunk.source_name}::{chunk.content[:64]}"
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        chunk_by_key[key] = chunk

    sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)
    return [
        chunk_by_key[key].model_copy(update={"score": rrf_scores[key]})
        for key in sorted_keys[:top_k]
    ]


async def search_collection_dense(
    *,
    question: str,
    collection: str,
    embedder: Embedder,
    vector_db: VectorDB,
    top_k: int = settings.search_top_k,
) -> list[RetrievedChunk]:
    vector = embedder.embed_dense([question])[0]
    hits = vector_db.search_dense(collection=collection, vector=vector, top_k=top_k)
    return [
        RetrievedChunk(
            content=str(payload.get("content", "")),
            source_name=str(payload.get("source_name", "")),
            format=str(payload.get("format", "")),
            page=int(payload["page"]) if payload.get("page") is not None else None,  # type: ignore[call-overload]
            section_header=str(payload["section_header"])
            if payload.get("section_header")
            else None,
            score=score,
        )
        for payload, score in hits
    ]
