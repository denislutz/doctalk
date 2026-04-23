class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model

    async def generate(self, system: str, user: str) -> str:
        # TODO: implement via anthropic SDK
        raise NotImplementedError
