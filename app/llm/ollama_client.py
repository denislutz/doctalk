import ollama


class OllamaClient:
    def __init__(self, base_url: str, model: str = "llama3.2:3b"):
        self.base_url = base_url
        self.model = model
        self.client = ollama.AsyncClient(host=base_url, timeout=120.0)

    async def generate(self, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        response = await self.client.chat(model=self.model, messages=messages)
        return str(response["message"]["content"])
