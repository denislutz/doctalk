class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # TODO: initialize SentenceTransformer
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        # TODO: implement
        raise NotImplementedError
