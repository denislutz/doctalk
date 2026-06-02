import openai
from deepeval.models.base_model import DeepEvalBaseLLM

from app.config import settings


class DeepSeekDeepevalLLM(DeepEvalBaseLLM):  # type: ignore[no-untyped-call]
    def __init__(self) -> None:
        self._client = openai.OpenAI(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
        )

    def get_model_name(self) -> str:
        return settings.deepseek_model

    def load_model(self, *args: object, **kwargs: object) -> openai.OpenAI:  # type: ignore[override]
        return self._client

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)
