from pydantic import BaseModel


class CollectionInfo(BaseModel):
    name: str
    description: str
    size: int
    metadata: dict[str, object] = {}


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
