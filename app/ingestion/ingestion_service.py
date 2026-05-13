import logging
from pathlib import Path

from app.ingestion.embedder import Embedder
from app.ingestion.file_loader_service import load_docx, load_epub, load_md, load_pdf, load_txt
from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

logger: logging.Logger = logging.getLogger(name=__name__)

_DISPATCH = {
    "pdf": load_pdf,
    "md": load_md,
    "docx": load_docx,
    "txt": load_txt,
    "epub": load_epub,
}


class IngestionService:
    def __init__(
        self, registry: DocRegistry, embedder: Embedder, vector_db_client: VectorDB
    ) -> None:
        self.registry: DocRegistry = registry
        self.embedder: Embedder = embedder
        self.vector_db_client: VectorDB = vector_db_client

    async def ingest(self, *, path: Path, topic: str, source_name: str) -> dict[str, object]:
        logger.debug(f"Ingesting {path}")

        contents = path.read_bytes()
        file_hash = self.registry.compute_hash(contents)
        if self.registry.is_duplicate(file_hash, topic):
            return {"skipped": True, "reason": "already indexed in this topic"}

        content_type = path.suffix.lstrip(".")
        loader = _DISPATCH.get(content_type)
        if loader is None:
            raise Exception(f"Unsupported file type: {content_type}")
        chunks = loader(path=str(path), source_name=source_name)

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

        doc_id: str = self.registry.insert_document(
            topic=topic,
            source_name=source_name,
            filename=path.name,
            format=content_type,
            file_hash=file_hash,
            chunk_count=len(chunks),
        )
        return {"doc_id": doc_id, "chunk_count": len(chunks), "topic": topic}
