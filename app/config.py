from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    api_key: str = "changeme"

    vector_db_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    ollama_url: str = "http://localhost:11434"
    default_llm_provider: str = "ollama"
    default_llm_model: str = "llama3.2:3b"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-haiku-20240307"

    embedding_model: str = "all-MiniLM-L6-v2"
    upload_dir: str = "/app/uploads"

    max_chunk_size: int = 512
    chunk_overlap: int = 50
    min_chunk_size: int = 50
    csv_rows_per_chunk: int = 25

    dense_top_k: int = 20
    sparse_top_k: int = 20
    rerank_top_k: int = 5
    use_reranking: bool = True

    class Config:
        env_file = (".env", ".env.local")
        extra = "ignore"


settings = Settings()
