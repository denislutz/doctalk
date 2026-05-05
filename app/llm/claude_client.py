# Provider: Anthropic SDK (anthropic>=0.30, already installed)
# Interface matches OllamaClient exactly so query.py can swap providers without branching.
# app.state.langchain_llm is set in main.py lifespan based on settings.default_llm_provider.
#
# Streaming variant (for /query/stream):
#   Use self.client.messages.stream() context manager → yields text_delta events.
#   async with self.client.messages.stream(...) as stream:
#       async for text in stream.text_stream:
#           yield text

from doctalk_shared.models import ChatMessage

LAST_N_HISTORY = 10


class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        # TODO: from anthropic import AsyncAnthropic
        # self.model = model
        # self.client = AsyncAnthropic(api_key=api_key)
        raise NotImplementedError

    async def generate(
        self, *, system_content: str, user_content: str, history: list[ChatMessage] | None = None
    ) -> str:
        # TODO:
        # 1. Build messages list from history[-LAST_N_HISTORY:] (role + content dicts)
        # 2. Append {"role": "user", "content": user_content}
        # 3. await self.client.messages.create(
        #        model=self.model, system=system_content,
        #        messages=messages, max_tokens=2048
        #    )
        # 4. return response.content[0].text
        raise NotImplementedError
