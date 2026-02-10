"""Tool Factory for creating and registering tools."""

from ..config import Settings
from ..services.search.task_block import TaskBlockSearchService
from ..services.search.web_search import WebSearchService
from .executors.clarify import ClarifyExecutor
from .executors.task_block_search import TaskBlockSearchExecutor
from .executors.web_search import WebSearchExecutor
from .registry import ToolRegistry


class ToolFactory:
    """Factory for creating and registering tool executors."""

    @staticmethod
    def create_all(settings: Settings) -> ToolRegistry:
        """
        Create all tools and register them.

        Args:
            settings: Application settings

        Returns:
            Configured ToolRegistry
        """
        registry = ToolRegistry()

        # Create search services
        web_search_service = WebSearchService(
            api_url=settings.web_search_api_url,
            api_key=settings.web_search_api_key,
        )
        task_block_service = TaskBlockSearchService(
            api_url=settings.task_block_search_url,
            api_key=settings.task_block_search_api_key,
        )

        # Create and register executors
        registry.register(WebSearchExecutor(web_search_service))
        registry.register(TaskBlockSearchExecutor(task_block_service))
        registry.register(ClarifyExecutor())

        return registry

    @staticmethod
    def create_web_search(settings: Settings) -> WebSearchExecutor:
        """Create web search executor."""
        service = WebSearchService(
            api_url=settings.web_search_api_url,
            api_key=settings.web_search_api_key,
        )
        return WebSearchExecutor(service)

    @staticmethod
    def create_task_block_search(settings: Settings) -> TaskBlockSearchExecutor:
        """Create task block search executor."""
        service = TaskBlockSearchService(
            api_url=settings.task_block_search_url,
            api_key=settings.task_block_search_api_key,
        )
        return TaskBlockSearchExecutor(service)

    @staticmethod
    def create_clarify() -> ClarifyExecutor:
        """Create clarify executor."""
        return ClarifyExecutor()
