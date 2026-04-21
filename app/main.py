from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import collections, health, query, upload
from app.config import settings
from app.ingestion.embedder import Embedder
from app.llm.ollama_client import OllamaClient
from app.storage.vector_db_client import VectorDB


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    app.state.embedder = Embedder(settings.embedding_model)
    app.state.vector_db_client = VectorDB(settings.vector_db_url)
    app.state.chat_model = OllamaClient(settings.ollama_url, settings.default_llm_model)
    yield


app = FastAPI(
    title="DocTalk API",
    description="Self-hosted RAG system for talking to your documents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(collections.router)
app.include_router(upload.router)
app.include_router(query.router)
