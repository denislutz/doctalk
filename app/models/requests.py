from pydantic import BaseModel


class DocumentUpload(BaseModel):
    topic: str
    description: str | None = None


class QueryRequest(BaseModel):
    question: str
    topics: list[str] | None = None
    top_k: int = 5
    use_reranking: bool = True
