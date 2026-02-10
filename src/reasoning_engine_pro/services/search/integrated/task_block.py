"""Task block search service using the integrated search endpoint."""

import json
from typing import Any, Optional

import httpx

from ....core.exceptions import ToolExecutionError
from ....core.schemas.tools import TaskBlockSearchResult
from ....observability.logger import get_logger
from .client import IntegratedSearchClient
from .response_parser import parse_task_block_search_results

logger = get_logger(__name__)


class IntegratedTaskBlockSearchService:
    """Task block search via the integrated search endpoint.

    Implements the same search(query) -> list[TaskBlockSearchResult]
    contract as TaskBlockSearchService.
    """

    def __init__(
        self,
        client: IntegratedSearchClient,
        max_results: int = 10,
        search_type: str = "llm",
        is_reason_required: bool = True,
        elastic_size: int = 5,
    ):
        self._client = client
        self._max_results = max_results
        self._search_type = search_type
        self._is_reason_required = is_reason_required
        self._elastic_size = elastic_size

    async def search(self, query: str) -> list[TaskBlockSearchResult]:
        """Search for task blocks via integrated endpoint."""
        try:
            request_body: dict[str, Any] = {
                "web_search": False,
                "rag_search": False,
                "opkey_qdrant_search": False,
                "web_search_tavily": False,
                "llm_task_block_search": self._search_type == "llm",
                "plain_elastic_task_block_search": self._search_type == "elastic",
            }

            if self._search_type == "llm":
                request_body["llm_task_block_search_params"] = {
                    "query": query,
                    "is_reason_required": self._is_reason_required,
                }
            else:
                request_body["plain_elastic_task_block_search_params"] = {
                    "query": query,
                    "size": self._elastic_size,
                }

            response_data = await self._client.search(request_body)

            return parse_task_block_search_results(
                response_data,
                search_type=self._search_type,
                max_results=self._max_results,
            )

        except ToolExecutionError:
            raise
        except httpx.TimeoutException:
            raise ToolExecutionError(
                "Integrated task block search request timed out",
                "task_block_search",
                {"query": query},
            )
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(
                f"Integrated task block search API error: {e.response.status_code}",
                "task_block_search",
                {"query": query, "status_code": e.response.status_code},
            )
        except httpx.HTTPError as e:
            raise ToolExecutionError(
                f"Integrated task block search HTTP error: {e}",
                "task_block_search",
                {"query": query},
            )
        except json.JSONDecodeError as e:
            raise ToolExecutionError(
                f"Integrated task block search response parse error: {e}",
                "task_block_search",
                {"query": query},
            )

    async def get_block_details(self, block_id: str) -> Optional[dict[str, Any]]:
        """Not supported via integrated endpoint."""
        logger.warning(
            "get_block_details not supported via integrated endpoint",
            block_id=block_id,
        )
        return None

    async def close(self) -> None:
        """No-op: the shared IntegratedSearchClient owns the HTTP lifecycle."""
