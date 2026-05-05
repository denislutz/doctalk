# MODEL: cross-encoder/ms-marco-MiniLM-L-6-v2
# The similarity search consisst of two steps
# BI Encoder, pure semantic similarity search, which is fast but may be inaccurate
# Cross Encoder, with a different model, which was trained to recognize relatedness between query and document
# - the cross encoder reranks the biencoder results to be more related to the actual question
# Rule of thumb and mental model
# bi encoder: do this two sencentes belong to same topic?
# cross encoder: does this text address this question?

from doctalk_shared.models import RetrievedChunk
from sentence_transformers import CrossEncoder

from app.config import settings

_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker:
    def __init__(self, model_name: str = _MODEL) -> None:
        self.model = CrossEncoder(model_name)

    def rerank(
        self, question: str, chunks: list[RetrievedChunk], top_k: int = settings.rerank_top_k
    ) -> list[RetrievedChunk]:
        pairs = [(question, chunk.content) for chunk in chunks]
        scores_for_chunks: list[float] = self.model.predict(pairs).tolist()
        ranked_chunks = sorted(
            zip(scores_for_chunks, chunks, strict=True), key=lambda x: x[0], reverse=True
        )

        return [chunk for _, chunk in ranked_chunks[:top_k]]
