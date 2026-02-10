"""Search service factory."""

from ...config import Settings
from .task_block import TaskBlockSearchService
from .web_search import WebSearchService


class SearchServiceFactory:
    """Factory for creating search services."""

    @staticmethod
    def create_web_search(settings: Settings) -> WebSearchService:
        """Create web search service from settings."""
        return WebSearchService(
            api_url=settings.web_search_api_url,
            api_key=settings.web_search_api_key,
            model=settings.web_search_model,
            max_tokens=settings.web_search_max_tokens,
        )

    @staticmethod
    def create_task_block_search(settings: Settings) -> TaskBlockSearchService:
        """Create task block search service from settings."""
        return TaskBlockSearchService(
            api_url=settings.task_block_search_url,
            api_key=settings.task_block_search_api_key,
        )
