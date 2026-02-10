"""LLM Provider Factory."""

from typing import Literal

from ..config import Settings
from ..core.interfaces.llm_provider import ILLMProvider
from .providers.openai import OpenAIProvider
from .providers.vllm import VLLMProvider


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create(
        provider_type: Literal["vllm", "openai"],
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: float = 120.0,
    ) -> ILLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider_type: Type of provider to create
            base_url: API base URL
            api_key: API key
            model_name: Model name to use
            timeout: Request timeout in seconds

        Returns:
            LLM provider instance
        """
        if provider_type == "vllm":
            return VLLMProvider(
                base_url=base_url,
                api_key=api_key,
                model_name=model_name,
                timeout=timeout,
            )
        elif provider_type == "openai":
            return OpenAIProvider(
                api_key=api_key,
                model_name=model_name,
                timeout=timeout,
            )
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    @staticmethod
    def create_from_settings(settings: Settings) -> ILLMProvider:
        """
        Create an LLM provider from application settings.

        Args:
            settings: Application settings

        Returns:
            LLM provider instance
        """
        return LLMProviderFactory.create(
            provider_type=settings.llm_provider,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model_name=settings.llm_model_name,
        )
