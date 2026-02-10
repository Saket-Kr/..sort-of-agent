"""Base search service with shared HTTP client lifecycle."""

from typing import Optional

import httpx


class BaseSearchService:
    """Base class for search services using httpx."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_results: int = 10,
    ):
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
