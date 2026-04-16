from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    topics: list[str] | None = None
    top_k: int = 5
    use_reranking: bool = True


@router.post("")
async def query(request: QueryRequest):
    # TODO: implement RAG pipeline
    return {
        "answer": "Not implemented yet.",
        "sources": [],
        "tokens_used": 0,
        "retrieval_time_ms": 0.0,
        "generation_time_ms": 0.0,
    }
