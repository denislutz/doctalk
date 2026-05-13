import logging
import tempfile
from pathlib import Path

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

    filename = file.filename or "upload"
    suffix = Path(filename).suffix
    contents = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        ingestion_service = IngestionService(
            registry=registry, embedder=embedder, vector_db_client=vector_db_client
        )
        return await ingestion_service.ingest(
            path=tmp_path,
            topic=topic,
            source_name=source_name or filename,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.delete("/{topic}")
async def delete_topic(request: Request, topic: str) -> dict[str, str]:
    vector_db_client: VectorDB = request.app.state.vector_db_client
    registry: DocRegistry = request.app.state.doc_registry
    vector_db_client.delete_collection(topic)
    registry.delete_topic(topic)
    return {"topic": topic}
