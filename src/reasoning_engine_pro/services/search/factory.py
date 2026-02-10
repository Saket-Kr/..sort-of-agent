"""Search service factory."""

from typing import Optional

from ...config import Settings
from .task_block import TaskBlockSearchService
from .web_search import WebSearchService


class SearchServiceFactory:
    """Factory for creating search services.

    Routes to the appropriate backend (legacy or integrated)
    based on config settings.
    """

    _integrated_client: Optional["IntegratedSearchClient"] = None

    @classmethod
    def _get_or_create_integrated_client(cls, settings: Settings):
        """Get or create the shared integrated search client."""
        if cls._integrated_client is None:
            from .integrated.client import IntegratedSearchClient

            cls._integrated_client = IntegratedSearchClient(
                api_url=settings.integrated_search_url,
                api_key=settings.integrated_search_api_key,
                timeout=settings.integrated_search_timeout,
            )
        return cls._integrated_client

    @staticmethod
    def create_web_search(settings: Settings):
        """Create web search service from settings."""
        if settings.web_search_backend == "integrated":
            from .integrated.web_search import IntegratedWebSearchService

            client = SearchServiceFactory._get_or_create_integrated_client(settings)
            return IntegratedWebSearchService(
                client=client,
                max_results=settings.integrated_web_search_max_results,
                model_type=settings.integrated_web_search_model_type,
            )

        return WebSearchService(
            api_url=settings.web_search_api_url,
            api_key=settings.web_search_api_key,
            model=settings.web_search_model,
            max_tokens=settings.web_search_max_tokens,
        )

    @staticmethod
    def create_task_block_search(settings: Settings):
        """Create task block search service from settings."""
        if settings.task_block_search_backend == "integrated":
            from .integrated.task_block import IntegratedTaskBlockSearchService

            client = SearchServiceFactory._get_or_create_integrated_client(settings)
            return IntegratedTaskBlockSearchService(
                client=client,
                search_type=settings.integrated_task_block_search_type,
                is_reason_required=settings.integrated_task_block_is_reason_required,
                elastic_size=settings.integrated_elastic_task_block_size,
            )

        return TaskBlockSearchService(
            api_url=settings.task_block_search_url,
            api_key=settings.task_block_search_api_key,
        )

    @classmethod
    async def close_integrated_client(cls) -> None:
        """Close the shared integrated client if it exists."""
        if cls._integrated_client is not None:
            await cls._integrated_client.close()
            cls._integrated_client = None

    @classmethod
    def reset(cls) -> None:
        """Reset factory state (for testing)."""
        cls._integrated_client = None
