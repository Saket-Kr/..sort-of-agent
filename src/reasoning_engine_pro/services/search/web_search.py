"""Web search service using Perplexity API."""

import json

import httpx

from ...core.exceptions import ToolExecutionError
from ...core.schemas.tools import WebSearchResult
from .base import BaseSearchService


class WebSearchService(BaseSearchService):
    """Web search service using Perplexity API."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_results: int = 5,
        model: str = "llama-3.1-sonar-small-128k-online",
        max_tokens: int = 1024,
    ):
        super().__init__(
            api_url=api_url,
            api_key=api_key,
            timeout=timeout,
            max_results=max_results,
        )
        self._model = model
        self._max_tokens = max_tokens

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

            response = await client.post(
                f"{self._api_url}/chat/completions",
                json={
                    "model": self._model,
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
                    "max_tokens": self._max_tokens,
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

            if "choices" in data and data["choices"]:
                message = data["choices"][0].get("message", {})
                content = message.get("content", "")

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
        except ToolExecutionError:
            raise
        except json.JSONDecodeError as e:
            raise ToolExecutionError(
                f"Web search response parse error: {str(e)}",
                "web_search",
                {"query": query},
            )
