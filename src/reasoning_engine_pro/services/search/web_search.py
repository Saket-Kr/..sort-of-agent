"""Web search service using Perplexity API."""

from typing import Optional

import httpx

from ...core.exceptions import ToolExecutionError
from ...core.schemas.tools import WebSearchResult


class WebSearchService:
    """Web search service using Perplexity API."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_results: int = 5,
    ):
        """
        Initialize web search service.

        Args:
            api_url: Perplexity API URL
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

    async def search(self, query: str) -> list[WebSearchResult]:
        """
        Execute web search query.

        Args:
            query: Search query string

        Returns:
            List of search results
        """
        try:
            client = await self._get_client()

            # Perplexity API request format
            response = await client.post(
                f"{self._api_url}/chat/completions",
                json={
                    "model": "llama-3.1-sonar-small-128k-online",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful search assistant. "
                                "Provide concise, factual information with sources."
                            ),
                        },
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 1024,
                    "return_citations": True,
                },
            )

            if response.status_code != 200:
                raise ToolExecutionError(
                    f"Web search API error: {response.status_code}",
                    "web_search",
                    {"status_code": response.status_code, "body": response.text},
                )

            data = response.json()
            results: list[WebSearchResult] = []

            # Parse Perplexity response
            if "choices" in data and data["choices"]:
                message = data["choices"][0].get("message", {})
                content = message.get("content", "")

                # Extract citations if available
                citations = data.get("citations", [])
                for i, citation in enumerate(citations[: self._max_results]):
                    results.append(
                        WebSearchResult(
                            title=citation.get("title", f"Result {i + 1}"),
                            url=citation.get("url", ""),
                            snippet=content[:500] if i == 0 else "",
                            source="perplexity",
                        )
                    )

                # If no citations, create a result from content
                if not results and content:
                    results.append(
                        WebSearchResult(
                            title=f"Search: {query[:50]}",
                            url="",
                            snippet=content[:500],
                            source="perplexity",
                        )
                    )

            return results

        except httpx.TimeoutException:
            raise ToolExecutionError(
                "Web search request timed out",
                "web_search",
                {"query": query},
            )
        except httpx.HTTPError as e:
            raise ToolExecutionError(
                f"Web search HTTP error: {str(e)}",
                "web_search",
                {"query": query},
            )
        except Exception as e:
            raise ToolExecutionError(
                f"Web search error: {str(e)}",
                "web_search",
                {"query": query},
            )
