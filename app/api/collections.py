from fastapi import APIRouter, Request

from app.storage.vector_db_client import VectorDB

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("")
async def list_collections(request: Request) -> list[str]:
    vector_db: VectorDB = request.app.state.vector_db_client
    return vector_db.list_collections()


@router.post("")
async def create_collection(request: Request, topic: str) -> dict[str, str]:
    vector_db: VectorDB = request.app.state.vector_db_client
    vector_db.ensure_collection(topic)
    return {"topic": topic, "status": "created"}


@router.get("/{topic}")
async def get_collection(request: Request, topic: str) -> dict[str, object]:
    vector_db: VectorDB = request.app.state.vector_db_client
    collection_data = vector_db.get_collection(topic)
    return {"topic": topic, "data": collection_data}


@router.delete("/{topic}")
async def delete_collection(request: Request, topic: str) -> dict[str, str]:
    vector_db: VectorDB = request.app.state.vector_db_client
    vector_db.delete_collection(topic)
    return {"topic": topic, "status": "deleted"}
