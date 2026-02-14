"""Tool Factory for creating and registering tools."""

from ..config import Settings
from ..services.search.factory import SearchServiceFactory
from .executors.clarify import ClarifyExecutor
from .executors.present_answer import PresentAnswerExecutor
from .executors.submit_workflow import SubmitWorkflowExecutor
from .executors.task_block_search import TaskBlockSearchExecutor
from .executors.think_approach import ThinkApproachExecutor
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

        web_search_service = SearchServiceFactory.create_web_search(settings)
        task_block_service = SearchServiceFactory.create_task_block_search(settings)

        registry.register(WebSearchExecutor(web_search_service))
        registry.register(TaskBlockSearchExecutor(task_block_service))
        registry.register(ClarifyExecutor())
        registry.register(ThinkApproachExecutor())
        registry.register(PresentAnswerExecutor())
        registry.register(SubmitWorkflowExecutor())

        return registry
