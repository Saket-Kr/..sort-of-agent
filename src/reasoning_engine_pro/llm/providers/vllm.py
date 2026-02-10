"""VLLM provider implementation (OpenAI-compatible)."""

from .base import BaseLLMProvider


class VLLMProvider(BaseLLMProvider):
    """VLLM provider using OpenAI-compatible API."""

    @property
    def _provider_name(self) -> str:
        return "VLLM"
