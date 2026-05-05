import logging

from doctalk_shared.models import CollectionInfo, IndexedDocument
from fastapi import APIRouter, Request

from app.storage.doc_registry import DocRecord, DocRegistry
from app.storage.vector_db_client import CollectionStats, VectorDB

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("")
async def list_collections(request: Request) -> list[CollectionInfo]:
    vector_db: VectorDB = request.app.state.vector_db_client
    collections = vector_db.list_collections()
    response_data = []
    for name in collections:
        stats: CollectionStats = vector_db.get_collection(name)
        # get the documents from registry for the collection
        registry: DocRegistry = request.app.state.doc_registry
        records: list[DocRecord] = registry.list_documents(name)
        documents = [
            IndexedDocument(
                doc_id=r.doc_id,
                source_name=r.source_name,
                filename=r.filename,
                format=r.format,
                chunk_count=r.chunk_count,
                ingested_at=r.ingested_at,
            )
            for r in records
        ]
        response_data.append(
            CollectionInfo(
                name=name,
                description="",
                size=stats.points_count,
                documents=documents,
                doc_count=len(documents),
            )
        )
    logger.info(f"Available collections: {len(response_data)}")
    return response_data


@router.post("")
async def create_collection(request: Request, topic: str) -> dict[str, str]:
    vector_db: VectorDB = request.app.state.vector_db_client
    vector_db.ensure_collection(topic)
    return {"topic": topic, "status": "created"}


@router.get("/{topic}")
async def get_collection(request: Request, topic: str) -> CollectionInfo:
    vector_db: VectorDB = request.app.state.vector_db_client
    registry: DocRegistry = request.app.state.doc_registry

    stats: CollectionStats = vector_db.get_collection(topic)
    logger.info(f"Collection stats for topic '{topic}': {stats}")

    # Fetch indexed documents from the registry (single SQL query, no Qdrant scroll needed).
    records: list[DocRecord] = registry.list_documents(topic)
    documents = [
        IndexedDocument(
            doc_id=r.doc_id,
            source_name=r.source_name,
            filename=r.filename,
            format=r.format,
            chunk_count=r.chunk_count,
            ingested_at=r.ingested_at,
        )
        for r in records
    ]

    return CollectionInfo(
        name=topic,
        description="",
        size=stats.points_count,
        doc_count=len(documents),
        documents=documents,
    )


@router.delete("/{topic}")
async def delete_collection(request: Request, topic: str) -> dict[str, str]:
    # delete collection from vector db
    vector_db: VectorDB = request.app.state.vector_db_client
    vector_db.delete_collection(topic)
    # delete all documents from the registry, to keep in sync
    registry: DocRegistry = request.app.state.doc_registry
    registry.delete_topic(topic)

    return {"topic": topic, "status": "deleted"}
