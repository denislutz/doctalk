class QdrantStore:
    def __init__(self, url: str, api_key: str | None = None):
        self.url = url
        self.api_key = api_key
        # TODO: initialize qdrant_client.QdrantClient

    async def list_collections(self) -> list[str]:
        # TODO: implement
        raise NotImplementedError

    async def create_collection(self, name: str, vector_size: int = 384) -> None:
        # TODO: implement
        raise NotImplementedError

    async def delete_collection(self, name: str) -> None:
        # TODO: implement
        raise NotImplementedError
