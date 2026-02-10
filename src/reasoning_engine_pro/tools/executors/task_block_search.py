"""Task Block Search tool executor."""

from typing import TYPE_CHECKING

from ...core.schemas.tools import (
    TaskBlockSearchInput,
    TaskBlockSearchOutput,
    TaskBlockSearchResult,
)
from .base import BaseToolExecutor

if TYPE_CHECKING:
    from ...services.search.task_block import TaskBlockSearchService


class TaskBlockSearchExecutor(
    BaseToolExecutor[TaskBlockSearchInput, TaskBlockSearchOutput]
):
    """Executor for task block search tool."""

    def __init__(self, search_service: "TaskBlockSearchService"):
        super().__init__(
            name="task_block_search",
            description=(
                "Search for available task blocks that can be used in workflows. "
                "Task blocks are pre-built automation components with specific actions."
            ),
        )
        self._search_service = search_service

    @property
    def input_schema(self) -> type[TaskBlockSearchInput]:
        return TaskBlockSearchInput

    @property
    def output_schema(self) -> type[TaskBlockSearchOutput]:
        return TaskBlockSearchOutput

    async def execute(self, input_data: TaskBlockSearchInput) -> TaskBlockSearchOutput:
        """Execute task block search queries."""
        all_results: list[TaskBlockSearchResult] = []

        for query in input_data.queries:
            results = await self._search_service.search(query)
            all_results.extend(results)

        # Deduplicate by block_id, keeping highest relevance score
        seen: dict[str, TaskBlockSearchResult] = {}
        for result in all_results:
            if (
                result.block_id not in seen
                or result.relevance_score > seen[result.block_id].relevance_score
            ):
                seen[result.block_id] = result

        unique_results = list(seen.values())
        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)

        return TaskBlockSearchOutput(
            results=unique_results,
            query_count=len(input_data.queries),
            total_results=len(unique_results),
        )
