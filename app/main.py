import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import collections, health, query, upload
from app.config import settings
from app.ingestion.embedder import Embedder
from app.llm.ollama_client import OllamaClient
from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

logger.info("Starting DocTalk API")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    app.state.embedder = Embedder(settings.embedding_model)
    app.state.vector_db_client = VectorDB(settings.vector_db_url)
    app.state.chat_model = OllamaClient(settings.ollama_url, settings.default_llm_model)
    # DocRegistry opens (or creates) the SQLite file and runs _init_db on startup.
    # The /app/data directory must exist — add it to Dockerfile and docker-compose volume.
    app.state.doc_registry = DocRegistry(settings.registry_db_path)
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
