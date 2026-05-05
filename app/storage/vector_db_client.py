from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)


class Chunkable(Protocol):
    content: str
    metadata: Any


@dataclass
class CollectionStats:
    name: str
    points_count: int
    config: object


class VectorDB:
    def __init__(self, url: str, api_key: str | None = None):
        self.client = QdrantClient(url=url, api_key=api_key)

    def is_present_collection(self, name: str) -> bool:
        return self.client.collection_exists(name)

    def ensure_collection(self, name: str, vector_size: int = 384) -> None:
        print(f"Creating collection...{name}")
        if not self.is_present_collection(name):
            self.client.create_collection(
                collection_name=name,
                vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
                sparse_vectors_config={
                    "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
                },
            )
            print(f"Collection created! {name}")

    def get_collection(self, name: str) -> CollectionStats:
        collection = self.client.get_collection(name)
        return CollectionStats(
            name=name,
            config=collection.config,
            points_count=collection.points_count or 0,
        )

    def upsert_chunks(
        self,
        collection: str,
        chunks: Sequence[Chunkable],
        dense_embeddings: list[list[float]],
        sparse_embeddings: list[dict[int, float]] | None = None,
    ) -> None:
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, dense_embeddings, strict=True)):
            payload: dict[str, object] = {"content": chunk.content}
            payload.update(chunk.metadata)
            vectors: dict[str, Any] = {"dense": embedding}
            if sparse_embeddings is not None:
                sparse = sparse_embeddings[i]
                vectors["sparse"] = {
                    "indices": list(sparse.keys()),
                    "values": list(sparse.values()),
                }
            point = PointStruct(id=uuid4(), vector=vectors, payload=payload)
            points.append(point)
        self.client.upsert(collection_name=collection, points=points)

    def search_dense(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 5,
    ) -> list[tuple[dict[str, object], float]]:
        response = self.client.query_points(
            collection_name=collection, query=vector, using="dense", limit=top_k
        )
        return [(point.payload or {}, point.score) for point in response.points]

    def search_sparse(
        self,
        collection: str,
        sparse_vector: dict[int, float],
        top_k: int = 5,
    ) -> list[tuple[dict[str, object], float]]:
        query = SparseVector(
            indices=list(sparse_vector.keys()),
            values=list(sparse_vector.values()),
        )
        response = self.client.query_points(
            collection_name=collection, query=query, using="sparse", limit=top_k
        )
        return [(point.payload or {}, point.score) for point in response.points]

    def list_collections(self) -> list[str]:
        response = self.client.get_collections()
        return [collection.name for collection in response.collections]

    def delete_collection(self, name: str) -> None:
        self.client.delete_collection(name)
