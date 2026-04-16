class OllamaClient:
    def __init__(self, base_url: str, model: str = "mistral:7b"):
        self.base_url = base_url
        self.model = model

    async def generate(self, prompt: str) -> str:
        # TODO: implement via ollama SDK
        raise NotImplementedError
