import ollama
from doctalk_shared.models import ChatMessage

LAST_N_HISTORY = 10


class OllamaClient:
    def __init__(self, base_url: str, model: str = "llama3.2:3b"):
        self.base_url = base_url
        self.model = model
        self.client = ollama.AsyncClient(host=base_url, timeout=120.0)

    async def generate(
        self, *, system_content: str, user_content: str, history: list[ChatMessage] | None = None
    ) -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        for msg in history[-LAST_N_HISTORY:] if history else []:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_content})
        response = await self.client.chat(model=self.model, messages=messages)
        return str(response["message"]["content"])
