"""Direct OpenAI provider implementation."""

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Direct OpenAI API provider."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4-turbo-preview",
        timeout: float = 120.0,
    ):
        super().__init__(
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
        )

    @property
    def _provider_name(self) -> str:
        return "OpenAI"
