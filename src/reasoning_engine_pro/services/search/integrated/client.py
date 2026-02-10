"""Shared HTTP client for the integrated search endpoint."""

from typing import Any, Optional

import httpx

from ....core.exceptions import ToolExecutionError
from ....observability.logger import get_logger

logger = get_logger(__name__)


class IntegratedSearchClient:
    """HTTP client for the integrated search endpoint.

    Manages a single httpx.AsyncClient instance shared by all
    integrated search services.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Authorization": self._api_key,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def search(self, request_body: dict[str, Any]) -> dict[str, Any]:
        """Execute a search request against the integrated endpoint.

        Args:
            request_body: Full JSON request body with boolean flags and params.

        Returns:
            Parsed JSON response from the endpoint.

        Raises:
            ToolExecutionError: On HTTP or parsing errors.
        """
        client = await self._get_client()

        active_flags = {k: v for k, v in request_body.items() if isinstance(v, bool) and v}
        logger.info(
            "Integrated search request",
            url=self._api_url,
            active_flags=list(active_flags.keys()),
        )

        response = await client.post(self._api_url, json=request_body)

        logger.debug(
            "Integrated search response",
            status_code=response.status_code,
            body_preview=response.text[:500] if response.text else "",
        )

        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
