import httpx
from fastapi import APIRouter, Request

from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    result: dict[str, str] = {"status": "ok", "service": "doctalk-api"}

    vector_db: VectorDB = request.app.state.vector_db_client
    try:
        vector_db.client.get_collections()
        result["qdrant"] = "ok"
    except Exception as e:
        result["qdrant"] = f"error: {e}"
        result["status"] = "degraded"

    llm = request.app.state.langchain_llm
    try:
        async with httpx.AsyncClient() as client:
            await client.get(llm.base_url, timeout=3.0)
        result["llm"] = "ok"
    except Exception as e:
        result["llm"] = f"error: {e}"
        result["status"] = "degraded"

    registry: DocRegistry = request.app.state.doc_registry
    try:
        registry.ping()
        result["registry"] = "ok"
    except Exception as e:
        result["registry"] = f"error: {e}"
        result["status"] = "degraded"

    return result
