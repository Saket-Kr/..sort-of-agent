"""Task block search service."""

from typing import Any, Optional

import httpx

from ...core.exceptions import ToolExecutionError
from ...core.schemas.tools import TaskBlockSearchResult


class TaskBlockSearchService:
    """Service for searching available task blocks."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_results: int = 10,
    ):
        """
        Initialize task block search service.

        Args:
            api_url: Task block API URL
            api_key: API key
            timeout: Request timeout in seconds
            max_results: Maximum results per query
        """
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._max_results = max_results
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(self, query: str) -> list[TaskBlockSearchResult]:
        """
        Search for task blocks matching query.

        Args:
            query: Search query string

        Returns:
            List of matching task blocks
        """
        try:
            client = await self._get_client()

            response = await client.post(
                f"{self._api_url}/search",
                json={
                    "query": query,
                    "limit": self._max_results,
                },
            )

            if response.status_code != 200:
                raise ToolExecutionError(
                    f"Task block search API error: {response.status_code}",
                    "task_block_search",
                    {"status_code": response.status_code, "body": response.text},
                )

            data = response.json()
            results: list[TaskBlockSearchResult] = []

            for item in data.get("results", [])[: self._max_results]:
                results.append(
                    TaskBlockSearchResult(
                        block_id=item.get("block_id", ""),
                        name=item.get("name", ""),
                        action_code=item.get("action_code", ""),
                        description=item.get("description"),
                        inputs=item.get("inputs", []),
                        outputs=item.get("outputs", []),
                        relevance_score=item.get("relevance_score", 0.0),
                    )
                )

            return results

        except httpx.TimeoutException:
            raise ToolExecutionError(
                "Task block search request timed out",
                "task_block_search",
                {"query": query},
            )
        except httpx.HTTPError as e:
            raise ToolExecutionError(
                f"Task block search HTTP error: {str(e)}",
                "task_block_search",
                {"query": query},
            )
        except Exception as e:
            if isinstance(e, ToolExecutionError):
                raise
            raise ToolExecutionError(
                f"Task block search error: {str(e)}",
                "task_block_search",
                {"query": query},
            )

    async def get_block_details(self, block_id: str) -> Optional[dict[str, Any]]:
        """
        Get detailed information about a specific block.

        Args:
            block_id: Block identifier

        Returns:
            Block details or None if not found
        """
        try:
            client = await self._get_client()

            response = await client.get(f"{self._api_url}/blocks/{block_id}")

            if response.status_code == 404:
                return None

            if response.status_code != 200:
                raise ToolExecutionError(
                    f"Task block API error: {response.status_code}",
                    "task_block_search",
                    {"status_code": response.status_code},
                )

            return response.json()

        except httpx.HTTPError as e:
            raise ToolExecutionError(
                f"Task block HTTP error: {str(e)}",
                "task_block_search",
                {"block_id": block_id},
            )
