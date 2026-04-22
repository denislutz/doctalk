import logging

from doctalk_shared.models import CollectionInfo
from fastapi import APIRouter, Request

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
    # get more data for each collection
    # 2026-04-22 13:18:42,501 DEBUG    app.api.collections: Collection data for 'Staatenlos': {'name': 'Staatenlos', 'config': CollectionConfig(params=CollectionParams(vectors=VectorParams(size=384, distance=<Distance.COSINE: 'Cosine'>, hnsw_config=None, quantization_config=None, on_disk=None, datatype=None, multivector_config=None), shard_number=1, sharding_method=None, replication_factor=1, write_consistency_factor=1, read_fan_out_factor=None, read_fan_out_delay_ms=None, on_disk_payload=True, sparse_vectors=None), hnsw_config=HnswConfig(m=16, ef_construct=100, full_scan_threshold=10000, max_indexing_threads=0, on_disk=False, payload_m=None, inline_storage=None), optimizer_config=OptimizersConfig(deleted_threshold=0.2, vacuum_min_vector_number=1000, default_segment_number=0, max_segment_size=None, memmap_threshold=None, indexing_threshold=10000, flush_interval_sec=5, max_optimization_threads=None, prevent_unoptimized=None), wal_config=WalConfig(wal_capacity_mb=32, wal_segments_ahead=0, wal_retain_closed=1), quantization_config=None, strict_mode_config=None, metadata=None), 'points_count': 144}
    response_data = []
    for collection in collections:
        stats: CollectionStats = vector_db.get_collection(collection)
        logger.debug(f"Collection data for '{collection}': {stats}")
        response_data.append(
            CollectionInfo(
                name=collection,
                description="",
                size=stats.points_count,
            )
        )
    logger.info(f"Available collections: {response_data}")
    return response_data


@router.post("")
async def create_collection(request: Request, topic: str) -> dict[str, str]:
    vector_db: VectorDB = request.app.state.vector_db_client
    vector_db.ensure_collection(topic)
    return {"topic": topic, "status": "created"}


@router.get("/{topic}")
async def get_collection(request: Request, topic: str) -> dict[str, object]:
    vector_db: VectorDB = request.app.state.vector_db_client
    stats: CollectionStats = vector_db.get_collection(topic)
    logger.info(f"Collection stats for topic '{topic}': {stats}")
    return {"topic": topic, "points_count": stats.points_count}


@router.delete("/{topic}")
async def delete_collection(request: Request, topic: str) -> dict[str, str]:
    vector_db: VectorDB = request.app.state.vector_db_client
    vector_db.delete_collection(topic)
    return {"topic": topic, "status": "deleted"}
