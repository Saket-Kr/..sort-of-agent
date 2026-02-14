"""Response parsers for the integrated search endpoint.

The integrated endpoint returns a JSON response with:
- "query": the query string
- "content": a string containing XML-like tagged sections for each search type
- "sources": list (usually empty)

Each section in "content" uses tags like <web_search>...</web_search> and contains
Python repr-style search result objects that need regex parsing.
"""

import re
from typing import Any

from ....core.schemas.tools import TaskBlockSearchResult, WebSearchResult
from ....observability.logger import get_logger

logger = get_logger(__name__)


def parse_web_search_results(
    response_data: dict[str, Any],
    max_results: int = 5,
) -> list[WebSearchResult]:
    """Parse web search results from integrated endpoint response."""
    content = response_data.get("content", "")
    if not isinstance(content, str):
        logger.warning("Unexpected response: content is not a string")
        return []

    section = _extract_section(content, "web_search")
    if not section:
        logger.warning(
            "No <web_search> section found in response",
            content_preview=content[:200],
        )
        return []

    results: list[WebSearchResult] = []
    for match in re.finditer(r"SearchResult\(", section):
        start = match.start()
        block = _extract_balanced_parens(section, start + len("SearchResult"))
        if not block:
            continue

        title = _extract_field(block, "title") or ""
        url = _extract_field(block, "url") or ""
        snippet = _extract_field(block, "snippet") or ""

        if title or url:
            results.append(WebSearchResult(
                title=title[:200],
                url=url,
                snippet=snippet[:500],
                source="integrated",
            ))

        if len(results) >= max_results:
            break

    return results


def parse_task_block_search_results(
    response_data: dict[str, Any],
    search_type: str = "llm",
    max_results: int = 10,
) -> list[TaskBlockSearchResult]:
    """Parse task block search results from integrated endpoint response."""
    content = response_data.get("content", "")
    if not isinstance(content, str):
        logger.warning("Unexpected response: content is not a string")
        return []

    # Try the specific section tag based on search type
    if search_type == "elastic":
        section = _extract_section(content, "plain_elastic_task_block_search")
    else:
        section = _extract_section(content, "llm_task_block_search")

    if not section:
        logger.warning(
            "No task block search section found in response",
            search_type=search_type,
            content_preview=content[:200],
        )
        return []

    # LLM task block search returns plain text summary, not structured results
    if search_type == "llm" and "TaskSearchResult(" not in section:
        return [TaskBlockSearchResult(
            block_id="llm-summary",
            name="LLM Search Summary",
            action_code="",
            description=section.strip()[:1000],
            relevance_score=1.0,
        )]

    # Parse structured TaskSearchResult objects (elastic search format)
    results: list[TaskBlockSearchResult] = []
    for match in re.finditer(r"TaskSearchResult\(", section):
        start = match.start()
        block = _extract_balanced_parens(section, start + len("TaskSearchResult"))
        if not block:
            continue

        block_id = _extract_field(block, "id") or ""
        name = _extract_field(block, "name") or ""
        action_code = _extract_field(block, "action_code") or ""
        description = _extract_field(block, "description") or ""
        score_str = _extract_numeric_field(block, "score") or "0"
        similarity_str = _extract_numeric_field(block, "similarity") or "0"

        results.append(TaskBlockSearchResult(
            block_id=block_id,
            name=name,
            action_code=action_code,
            description=description[:1000] if description else None,
            relevance_score=float(similarity_str or score_str or 0),
        ))

        if len(results) >= max_results:
            break

    return results


def _extract_section(content: str, tag: str) -> str | None:
    """Extract content between <tag>...</tag> from the response content string."""
    pattern = rf"<{re.escape(tag)}>\s*(.*?)\s*</{re.escape(tag)}>"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else None


def _extract_balanced_parens(text: str, start: int) -> str | None:
    """Extract the content of balanced parentheses starting at position `start`."""
    if start >= len(text) or text[start] != "(":
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return None


def _extract_field(block: str, field_name: str) -> str | None:
    """Extract a string field value from a repr-style block like `field='value'`."""
    pattern = rf"{field_name}='((?:[^'\\]|\\.)*)'"
    match = re.search(pattern, block)
    if match:
        return match.group(1).replace("\\'", "'").replace("\\n", "\n")
    # Try double quotes
    pattern = rf'{field_name}="((?:[^"\\]|\\.)*)"'
    match = re.search(pattern, block)
    if match:
        return match.group(1).replace('\\"', '"').replace("\\n", "\n")
    return None


def _extract_numeric_field(block: str, field_name: str) -> str | None:
    """Extract a numeric field value from a repr-style block like `field=0.95`."""
    pattern = rf"{field_name}=([\d.]+)"
    match = re.search(pattern, block)
    return match.group(1) if match else None
