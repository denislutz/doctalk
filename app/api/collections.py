from fastapi import APIRouter

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("")
async def list_collections():
    # TODO: implement
    return []


@router.post("")
async def create_collection(topic: str):
    # TODO: implement
    return {"topic": topic, "status": "created"}


@router.get("/{topic}")
async def get_collection(topic: str):
    # TODO: implement
    return {"topic": topic}


@router.delete("/{topic}")
async def delete_collection(topic: str):
    # TODO: implement
    return {"topic": topic, "status": "deleted"}
