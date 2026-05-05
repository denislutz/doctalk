import logging
import pathlib
from contextlib import asynccontextmanager

from doctalk_shared.log_setup import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import ChatOllama

from app.api import collections, health, query, upload
from app.config import settings
from app.ingestion.embedder import Embedder
from app.retrieval.reranker import Reranker
from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

setup_logging("api.log", log_dir=pathlib.Path(__file__).resolve().parents[1] / "logs")

logger = logging.getLogger(__name__)

logger.info("Starting DocTalk API")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    app.state.vector_db_client = VectorDB(settings.vector_db_url)
    app.state.embedder = Embedder(settings.embedding_model)
    app.state.reranker = Reranker(model_name=settings.reranker_model)
    app.state.langchain_llm = ChatOllama(
        base_url=settings.langchain_llm_url, model=settings.default_llm_model
    )
    app.state.doc_registry = DocRegistry(settings.registry_db_path)
    logger.info("DocRegistry ready at %s", settings.registry_db_path)
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
