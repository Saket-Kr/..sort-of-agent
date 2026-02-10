"""Web Search tool executor."""

from typing import TYPE_CHECKING

from ...core.schemas.tools import WebSearchInput, WebSearchOutput, WebSearchResult
from .base import BaseToolExecutor

if TYPE_CHECKING:
    from ...services.search.web_search import WebSearchService


class WebSearchExecutor(BaseToolExecutor[WebSearchInput, WebSearchOutput]):
    """Executor for web search tool."""

    def __init__(self, search_service: "WebSearchService"):
        super().__init__(
            name="web_search",
            description=(
                "Search the web for information about enterprise systems, business processes, "
                "technical details, and domain-specific knowledge."
            ),
        )
        self._search_service = search_service

    @property
    def input_schema(self) -> type[WebSearchInput]:
        return WebSearchInput

    @property
    def output_schema(self) -> type[WebSearchOutput]:
        return WebSearchOutput

    async def execute(self, input_data: WebSearchInput) -> WebSearchOutput:
        """Execute web search queries."""
        all_results: list[WebSearchResult] = []

        for query in input_data.queries:
            results = await self._search_service.search(query)
            all_results.extend(results)

        return WebSearchOutput(
            results=all_results,
            query_count=len(input_data.queries),
            total_results=len(all_results),
        )
