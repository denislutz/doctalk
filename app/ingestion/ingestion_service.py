import logging
import os
import tempfile

from fastapi import UploadFile

from app.ingestion.embedder import Embedder
from app.ingestion.file_loader_service import load_docx, load_epub, load_md, load_pdf, load_txt
from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self, registry: DocRegistry, embedder: Embedder, vector_db_client: VectorDB
    ) -> None:
        self.registry = registry
        self.embedder = embedder
        self.vector_db_client = vector_db_client

    async def ingest(self, *, file: UploadFile, topic: str, source_name: str) -> dict[str, object]:
        if not file or not file.filename:
            raise ValueError("No file provided")
        logger.debug(f"Uploading file {file.filename}")

        contents = await file.read()

        file_hash = self.registry.compute_hash(contents)
        if self.registry.is_duplicate(file_hash, topic):
            return {"skipped": True, "reason": "already indexed in this topic"}

        content_type = file.filename.split(".")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{content_type}") as temp_file:
            temp_file.write(contents)
            path = temp_file.name

        dispatch = {
            "pdf": load_pdf,
            "md": load_md,
            "docx": load_docx,
            "txt": load_txt,
            "epub": load_epub,
        }
        loader = dispatch.get(content_type)
        if loader is None:
            raise Exception(f"Unsupported file type: {content_type}")
        chunks = loader(path=path, source_name=source_name or file.filename)

        os.unlink(path)

        chunked_texts = [chunk.content for chunk in chunks]
        dense_embeddings = self.embedder.embed_dense(chunked_texts)
        sparse_embeddings = self.embedder.embed_sparse(chunked_texts)

        self.vector_db_client.ensure_collection(name=topic)
        self.vector_db_client.upsert_chunks(
            collection=topic,
            chunks=chunks,
            dense_embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
        )

        doc_id = self.registry.insert_document(
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
