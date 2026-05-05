from typing import Literal

from pydantic import BaseModel

# --- Upload ---


class DocumentUpload(BaseModel):
    topic: str
    description: str | None = None


# --- Query ---


class ChatMessage(BaseModel):
    # role must be "user" or "assistant" — maps directly to ollama/openai message roles
    role: Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    question: str
    topics: list[str] | None = None
    top_k: int = 5
    use_reranking: bool = True
    # history: prior turns in the conversation, oldest first.
    # Only the current question gets RAG context injected; history is passed as-is.
    history: list[ChatMessage] = []


class RetrievedChunk(BaseModel):
    content: str
    source_name: str
    format: str
    page: int | None = None
    section_header: str | None = None
    score: float


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


class IndexedDocument(BaseModel):
    doc_id: str
    source_name: str
    filename: str
    format: str
    chunk_count: int
    ingested_at: str  # ISO-8601 UTC


class CollectionInfo(BaseModel):
    name: str
    description: str
    size: int  # total chunk count from Qdrant
    formats: list[str] = []
    doc_count: int = 0
    documents: list[IndexedDocument] = []  # populated by GET /collections/{topic}
    metadata: dict[str, object] = {}


# --- Metadata Extraction ---


class ExtractedMetadata(BaseModel):
    title: str | None
    author: str | None
    source: Literal["file_metadata", "llm", "filename"]
    confidence: Literal["high", "medium", "low"]
