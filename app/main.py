import logging
import pathlib
from contextlib import asynccontextmanager

from doctalk_shared.log_setup import setup_logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

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

    # pick the configured llm model deepseek vs default

    langchain_llm: BaseChatModel
    if settings.default_llm_provider == "deepseek":
        logger.info("Using DeepSeek as LLM provider")
        langchain_llm = ChatOpenAI(
            api_key=SecretStr(settings.deepseek_api_key or "none"),
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            temperature=0,
        )
    else:
        logger.info("Using Ollama as LLM provider")
        langchain_llm = ChatOllama(
            base_url=settings.default_llm_url, model=settings.default_llm_model
        )

    app.state.langchain_llm = langchain_llm
    app.state.doc_registry = DocRegistry(settings.registry_db_path)
    logger.info("DocRegistry ready at %s", settings.registry_db_path)
    yield


app = FastAPI(
    title="DocTalk API",
    description="Self-hosted RAG system for talking to your documents",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
