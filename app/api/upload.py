import os
import tempfile

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.ingestion import chunker, loader_pdf
from app.storage.vector_db_client import VectorDB

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/{topic}")
async def upload_document(
    request: Request,
    topic: str,
    file: UploadFile = File(...),  # noqa: B008
    source_name: str = Form(None),
) -> dict[str, object] | None:
    if file and file.filename:
        content_type = file.filename.split(".")[-1]
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{content_type}") as temp_file:
            temp_file.write(contents)
            file_path = temp_file.name
        print(f"File path: {file_path} {file.filename}")
        if content_type == "pdf":
            long_content = loader_pdf.load_pdf(
                path=file_path, source_name=source_name or file.filename
            )
            os.unlink(file_path)
            chunks = chunker.chunk(long_content)

            embedder = request.app.state.embedder
            embeddings = embedder.embed([chunk.content for chunk in chunks])

            vector_db_client: VectorDB = request.app.state.vector_db_client
            vector_db_client.ensure_collection(name=topic)
            vector_db_client.upsert_chunks(collection=topic, chunks=chunks, embeddings=embeddings)
            return {
                "doc_id": file.filename,
                "chunk_count": len(chunks),
                "topic": topic,
            }
    return None


@router.delete("/{topic}")
async def delete_topic(request: Request, topic: str) -> dict[str, str]:
    vector_db_client: VectorDB = request.app.state.vector_db_client
    vector_db_client.delete_collection(topic)
    return {"topic": topic}
