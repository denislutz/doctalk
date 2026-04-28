import logging
import os
import tempfile
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.ingestion import chunker, loader_md, loader_pdf
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
) -> dict[str, object] | None:
    if file and file.filename:
        logger.debug(f"Uploading file {file.filename}")
        content_type = file.filename.split(".")[-1]
        contents = await file.read()

        registry: DocRegistry = request.app.state.doc_registry

        # --- Duplicate guard ---
        # TODO: compute hash with DocRegistry.compute_hash(contents)
        #       call registry.is_duplicate(file_hash, topic)
        #       if True → raise HTTPException(409, "Document already indexed in this topic")
        file_hash = DocRegistry.compute_hash(contents)
        if registry.is_duplicate(file_hash, topic):
            raise HTTPException(status_code=409, detail="Document already indexed in this topic")

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{content_type}") as temp_file:
            temp_file.write(contents)
            file_path = temp_file.name

        if content_type == "pdf":
            long_content = loader_pdf.load(path=file_path, source_name=source_name or file.filename)
        if content_type == "md":
            long_content = loader_md.load(path=file_path, source_name=source_name or file.filename)

        os.unlink(file_path)
        chunks = chunker.chunk(long_content)

        embedder = request.app.state.embedder
        embeddings = embedder.embed([chunk.content for chunk in chunks])

        vector_db_client: VectorDB = request.app.state.vector_db_client
        vector_db_client.ensure_collection(name=topic)
        vector_db_client.upsert_chunks(collection=topic, chunks=chunks, embeddings=embeddings)

        # --- Registry insert ---
        # Must happen AFTER successful Qdrant upsert so the registry only records
        # documents that are actually searchable. If upsert raises, we skip this.

        doc_id = str(uuid4())
        registry.insert_document(
            doc_id=doc_id,
            topic=topic,
            source_name=source_name or file.filename,
            filename=file.filename,
            format=content_type,
            file_hash=file_hash,
            chunk_count=len(chunks),
        )

        return {
            "doc_id": doc_id,
            "chunk_count": len(chunks),
            "topic": topic,
        }
    return None


@router.delete("/{topic}")
async def delete_topic(request: Request, topic: str) -> dict[str, str]:
    vector_db_client: VectorDB = request.app.state.vector_db_client
    vector_db_client.delete_collection(topic)
    return {"topic": topic}
