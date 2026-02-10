"""Task block search service."""

import json
from typing import Any, Optional

import httpx

from ...core.exceptions import ToolExecutionError
from ...core.schemas.tools import TaskBlockSearchResult
from .base import BaseSearchService


class TaskBlockSearchService(BaseSearchService):
    """Service for searching available task blocks."""

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
        except ToolExecutionError:
            raise
        except json.JSONDecodeError as e:
            raise ToolExecutionError(
                f"Task block search response parse error: {str(e)}",
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
