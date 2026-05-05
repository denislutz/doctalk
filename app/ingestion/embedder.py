from sentence_transformers import SentenceTransformer


# The similarity search consisst of two steps
# BI Encoder, pure semantic similarity search, which is fast but may be inaccurate
# Cross Encoder, with a different model, which was trained to recognize relatedness between query and document
# - the cross encoder reranks the biencoder results to be more related to the actual question
# Rule of thumb and mental model
# bi encoder: do this two sencentes belong to same topic?
# cross encoder: does this text address this question?
# This class implements the bi encoder with this embedder
class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()  # type: ignore[no-any-return]

    def embed_sparse(self, texts: list[str]) -> list[dict[int, float]]:
        # here we implement directly the terms frequency algo
        results = []
        for text in texts:
            tokens = text.lower().split()
            tf: dict[int, float] = {}  # setup the frequence dict
            for token in tokens:
                term_id = hash(token) % (2**20)
                # get the previous count for this token and increase
                tf[term_id] = tf.get(term_id, 0.0) + 1.0
            results.append(tf)
        return results
