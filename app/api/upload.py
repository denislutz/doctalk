import logging

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.ingestion.embedder import Embedder
from app.ingestion.ingestion_service import IngestionService
from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

router = APIRouter(prefix="/upload", tags=["upload"])

logger = logging.getLogger(__name__)


@router.post("/{topic}")
async def upload_document(
    request: Request,
    topic: str,
    file: UploadFile = File(...),  # noqa: B008
    source_name: str = Form(None),
) -> dict[str, object]:

    registry: DocRegistry = request.app.state.doc_registry
    embedder: Embedder = request.app.state.embedder
    vector_db_client: VectorDB = request.app.state.vector_db_client

    ingestion_service = IngestionService(
        registry=registry, embedder=embedder, vector_db_client=vector_db_client
    )
    return await ingestion_service.ingest(file=file, topic=topic, source_name=source_name)


@router.delete("/{topic}")
async def delete_topic(request: Request, topic: str) -> dict[str, str]:
    vector_db_client: VectorDB = request.app.state.vector_db_client
    registry: DocRegistry = request.app.state.doc_registry
    vector_db_client.delete_collection(topic)
    registry.delete_topic(topic)
    return {"topic": topic}
