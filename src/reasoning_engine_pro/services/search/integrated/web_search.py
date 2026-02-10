"""Web search service using the integrated search endpoint."""

import json

import httpx

from ....core.exceptions import ToolExecutionError
from ....core.schemas.tools import WebSearchResult
from ....observability.logger import get_logger
from .client import IntegratedSearchClient
from .response_parser import parse_web_search_results

logger = get_logger(__name__)


class IntegratedWebSearchService:
    """Web search via the integrated search endpoint.

    Implements the same search(query) -> list[WebSearchResult] contract
    as WebSearchService, but routes through the unified endpoint.
    """

    def __init__(
        self,
        client: IntegratedSearchClient,
        max_results: int = 3,
        model_type: str = "big",
    ):
        self._client = client
        self._max_results = max_results
        self._model_type = model_type

    async def search(self, query: str) -> list[WebSearchResult]:
        """Execute web search via integrated endpoint."""
        try:
            request_body = {
                "web_search": True,
                "rag_search": False,
                "opkey_qdrant_search": False,
                "web_search_tavily": False,
                "llm_task_block_search": False,
                "plain_elastic_task_block_search": False,
                "web_search_params": {
                    "query": query,
                    "max_results": self._max_results,
                    "include_snippets": True,
                    "use_search_handler": True,
                    "use_reranker": False,
                    "summarize_content": False,
                    "model_type": self._model_type,
                },
            }

            response_data = await self._client.search(request_body)

            return parse_web_search_results(
                response_data,
                max_results=self._max_results,
            )

        except ToolExecutionError:
            raise
        except httpx.TimeoutException:
            raise ToolExecutionError(
                "Integrated web search request timed out",
                "web_search",
                {"query": query},
            )
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(
                f"Integrated web search API error: {e.response.status_code}",
                "web_search",
                {"query": query, "status_code": e.response.status_code},
            )
        except httpx.HTTPError as e:
            raise ToolExecutionError(
                f"Integrated web search HTTP error: {e}",
                "web_search",
                {"query": query},
            )
        except json.JSONDecodeError as e:
            raise ToolExecutionError(
                f"Integrated web search response parse error: {e}",
                "web_search",
                {"query": query},
            )

    async def close(self) -> None:
        """No-op: the shared IntegratedSearchClient owns the HTTP lifecycle."""
