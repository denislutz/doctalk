from typing import Literal

from pydantic import BaseModel

# --- Upload ---


class DocumentUpload(BaseModel):
    topic: str
    description: str | None = None


# --- Query ---


class QueryRequest(BaseModel):
    question: str
    topics: list[str] | None = None
    top_k: int = 5
    use_reranking: bool = True


class SourceChunk(BaseModel):
    source_name: str
    format: str
    page_number: int | None = None
    section_header: str | None = None
    content_snippet: str
    relevance_score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    tokens_used: int
    retrieval_time_ms: float
    generation_time_ms: float


# --- Collections ---


class CollectionInfo(BaseModel):
    name: str
    description: str
    size: int
    formats: list[str] = []
    doc_count: int = 0
    metadata: dict[str, object] = {}


# --- Metadata Extraction ---


class ExtractedMetadata(BaseModel):
    title: str | None
    author: str | None
    source: Literal["file_metadata", "llm", "filename"]
    confidence: Literal["high", "medium", "low"]
