from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import collections, health, query, upload
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: initialize Qdrant client, embedder, etc.
    yield
    # TODO: cleanup


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
