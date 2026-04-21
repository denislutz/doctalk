import ollama


class OllamaClient:
    def __init__(self, base_url: str, model: str = "llama3.2:3b"):
        self.base_url = base_url
        self.model = model
        self.client = ollama.AsyncClient(host=base_url, timeout=120.0)

    async def generate(self, prompt: str) -> str:
        response = await self.client.generate(model=self.model, prompt=prompt)
        return str(response["response"])
