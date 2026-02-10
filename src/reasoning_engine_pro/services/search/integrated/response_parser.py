"""Response parsers for the integrated search endpoint.

The integrated endpoint response format may vary. These parsers
try multiple plausible key names and return empty lists on
unparseable responses rather than crashing.
"""

from typing import Any

from ....core.schemas.tools import TaskBlockSearchResult, WebSearchResult
from ....observability.logger import get_logger

logger = get_logger(__name__)


def parse_web_search_results(
    response_data: dict[str, Any],
    max_results: int = 5,
) -> list[WebSearchResult]:
    """Parse web search results from integrated endpoint response."""
    raw_results = (
        response_data.get("web_search_results")
        or _extract_nested(response_data, "web_search", "results")
        or response_data.get("results")
    )

    if not isinstance(raw_results, list):
        logger.warning(
            "Unexpected web search response format",
            keys=list(response_data.keys()) if isinstance(response_data, dict) else str(type(response_data)),
        )
        # Fallback: if there is a summary string, return it as a single result
        summary = (
            response_data.get("summary")
            or response_data.get("content")
            or _extract_nested(response_data, "web_search", "summary")
        )
        if summary:
            return [WebSearchResult(
                title="Integrated Search Result",
                url="",
                snippet=str(summary)[:500],
                source="integrated",
            )]
        return []

    results: list[WebSearchResult] = []
    for i, item in enumerate(raw_results[:max_results]):
        if isinstance(item, dict):
            results.append(WebSearchResult(
                title=item.get("title", f"Result {i + 1}"),
                url=item.get("url", item.get("link", "")),
                snippet=item.get("snippet", item.get("description", item.get("content", "")))[:500],
                source="integrated",
            ))

    return results


def parse_task_block_search_results(
    response_data: dict[str, Any],
    search_type: str = "llm",
    max_results: int = 10,
) -> list[TaskBlockSearchResult]:
    """Parse task block search results from integrated endpoint response."""
    key = f"{search_type}_task_block_search_results"
    alt_key = "plain_elastic_task_block_search_results" if search_type == "elastic" else key

    raw_results = (
        response_data.get(key)
        or response_data.get(alt_key)
        or _extract_nested(response_data, f"{search_type}_task_block_search", "results")
        or response_data.get("task_block_results")
        or response_data.get("results")
    )

    if not isinstance(raw_results, list):
        logger.warning(
            "Unexpected task block search response format",
            search_type=search_type,
            keys=list(response_data.keys()) if isinstance(response_data, dict) else str(type(response_data)),
        )
        return []

    results: list[TaskBlockSearchResult] = []
    for item in raw_results[:max_results]:
        if isinstance(item, dict):
            results.append(TaskBlockSearchResult(
                block_id=item.get("block_id", item.get("id", "")),
                name=item.get("name", ""),
                action_code=item.get("action_code", item.get("actionCode", "")),
                description=item.get("description"),
                inputs=item.get("inputs", []),
                outputs=item.get("outputs", []),
                relevance_score=float(item.get("relevance_score", item.get("score", 0.0))),
            ))

    return results


def _extract_nested(data: dict[str, Any], *keys: str) -> Any:
    """Safely extract nested dict value."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current
