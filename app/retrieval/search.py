async def search_collection(question: str, collection: str, top_k: int = 20) -> list[dict]:
    # TODO: implement dense + sparse search via Qdrant
    raise NotImplementedError


async def search_across_collections(
    question: str,
    topics: list[str] | None,
    top_k: int = 5,
) -> list[dict]:
    # TODO: implement multi-collection parallel search + RRF merge
    raise NotImplementedError
