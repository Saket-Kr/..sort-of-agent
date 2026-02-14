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
        """Create planner LLM provider from settings. Alias for create_planner_from_settings."""
        return LLMProviderFactory.create_planner_from_settings(settings)

    @staticmethod
    def create_planner_from_settings(settings: Settings) -> ILLMProvider:
        """Create the planner (primary reasoning) LLM provider from settings."""
        return LLMProviderFactory.create(
            provider_type=settings.planner_llm_provider,
            base_url=settings.planner_llm_base_url,
            api_key=settings.planner_llm_api_key,
            model_name=settings.planner_llm_model_name,
        )

    @staticmethod
    def create_validator_from_settings(settings: Settings) -> ILLMProvider:
        """Create the validator (cheaper) LLM provider from settings.

        Used for validation, referencing, summarization, and job naming.
        Uses the same provider type as planner but with separate URL/key/model.
        """
        return LLMProviderFactory.create(
            provider_type=settings.planner_llm_provider,
            base_url=settings.validator_llm_base_url,
            api_key=settings.validator_llm_api_key,
            model_name=settings.validator_llm_model_name,
        )
