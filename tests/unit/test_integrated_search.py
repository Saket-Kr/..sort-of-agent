"""Tests for integrated search services."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from reasoning_engine_pro.config import Settings
from reasoning_engine_pro.core.exceptions import ToolExecutionError
from reasoning_engine_pro.core.schemas.tools import TaskBlockSearchResult, WebSearchResult
from reasoning_engine_pro.services.search.integrated.client import IntegratedSearchClient
from reasoning_engine_pro.services.search.integrated.response_parser import (
    parse_task_block_search_results,
    parse_web_search_results,
)
from reasoning_engine_pro.services.search.integrated.task_block import (
    IntegratedTaskBlockSearchService,
)
from reasoning_engine_pro.services.search.integrated.web_search import (
    IntegratedWebSearchService,
)


# --- Response Parser Tests ---


class TestParseWebSearchResults:
    """Tests for web search response parser."""

    def test_standard_format(self):
        """Test parsing with expected key name."""
        response = {
            "web_search_results": [
                {"title": "Result 1", "url": "https://example.com/1", "snippet": "Snippet 1"},
                {"title": "Result 2", "url": "https://example.com/2", "snippet": "Snippet 2"},
            ]
        }
        results = parse_web_search_results(response, max_results=5)
        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].url == "https://example.com/1"
        assert results[0].source == "integrated"

    def test_nested_format(self):
        """Test parsing with nested web_search.results key."""
        response = {
            "web_search": {
                "results": [
                    {"title": "Nested", "url": "https://example.com", "snippet": "Nested snippet"},
                ]
            }
        }
        results = parse_web_search_results(response)
        assert len(results) == 1
        assert results[0].title == "Nested"

    def test_fallback_results_key(self):
        """Test parsing with generic 'results' key."""
        response = {
            "results": [
                {"title": "Generic", "url": "https://example.com", "snippet": "Generic snippet"},
            ]
        }
        results = parse_web_search_results(response)
        assert len(results) == 1

    def test_summary_fallback(self):
        """Test fallback to summary when results aren't a list."""
        response = {"summary": "This is a summary of the search."}
        results = parse_web_search_results(response)
        assert len(results) == 1
        assert "summary" in results[0].snippet.lower()

    def test_empty_on_unparseable(self):
        """Test graceful empty return for unexpected format."""
        response = {"unexpected_key": 123}
        results = parse_web_search_results(response)
        assert results == []

    def test_max_results_limit(self):
        """Test that max_results is respected."""
        response = {
            "web_search_results": [
                {"title": f"Result {i}", "url": f"https://example.com/{i}", "snippet": f"Snippet {i}"}
                for i in range(10)
            ]
        }
        results = parse_web_search_results(response, max_results=3)
        assert len(results) == 3

    def test_alternative_field_names(self):
        """Test parsing with 'link' instead of 'url' and 'description' instead of 'snippet'."""
        response = {
            "web_search_results": [
                {"title": "Alt", "link": "https://alt.com", "description": "Alt desc"},
            ]
        }
        results = parse_web_search_results(response)
        assert results[0].url == "https://alt.com"
        assert results[0].snippet == "Alt desc"


class TestParseTaskBlockSearchResults:
    """Tests for task block search response parser."""

    def test_llm_format(self):
        """Test parsing LLM task block results."""
        response = {
            "llm_task_block_search_results": [
                {
                    "block_id": "export-config",
                    "name": "Export Config",
                    "action_code": "ExportConfigurations",
                    "relevance_score": 0.95,
                },
            ]
        }
        results = parse_task_block_search_results(response, search_type="llm")
        assert len(results) == 1
        assert results[0].block_id == "export-config"
        assert results[0].action_code == "ExportConfigurations"

    def test_elastic_format(self):
        """Test parsing elastic task block results."""
        response = {
            "plain_elastic_task_block_search_results": [
                {
                    "block_id": "import-data",
                    "name": "Import Data",
                    "action_code": "ImportData",
                    "score": 0.8,
                },
            ]
        }
        results = parse_task_block_search_results(response, search_type="elastic")
        assert len(results) == 1
        assert results[0].block_id == "import-data"
        assert results[0].relevance_score == 0.8

    def test_alternative_field_names(self):
        """Test parsing with 'id' instead of 'block_id', 'actionCode' instead of 'action_code'."""
        response = {
            "llm_task_block_search_results": [
                {
                    "id": "alt-block",
                    "name": "Alt Block",
                    "actionCode": "AltAction",
                    "score": 0.7,
                },
            ]
        }
        results = parse_task_block_search_results(response, search_type="llm")
        assert results[0].block_id == "alt-block"
        assert results[0].action_code == "AltAction"

    def test_empty_on_unparseable(self):
        """Test graceful empty return for unexpected format."""
        response = {"unexpected": "data"}
        results = parse_task_block_search_results(response, search_type="llm")
        assert results == []


# --- IntegratedSearchClient Tests ---


class TestIntegratedSearchClient:
    """Tests for the shared HTTP client."""

    @pytest.fixture
    def client(self):
        return IntegratedSearchClient(
            api_url="http://test-host:443/integrated-search",
            api_key="pk_test_key",
            timeout=10.0,
        )

    @pytest.mark.asyncio
    async def test_search_success(self, client):
        """Test successful search call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"results": []}'
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        result = await client.search({"web_search": True})

        mock_http_client.post.assert_called_once_with(
            "http://test-host:443/integrated-search",
            json={"web_search": True},
        )
        assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_auth_header_format(self, client):
        """Test that auth header uses raw key (not Bearer)."""
        http_client = await client._get_client()
        assert http_client.headers["Authorization"] == "pk_test_key"

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test client cleanup."""
        mock_http_client = AsyncMock()
        client._client = mock_http_client
        await client.close()
        mock_http_client.aclose.assert_called_once()
        assert client._client is None


# --- IntegratedWebSearchService Tests ---


class TestIntegratedWebSearchService:
    """Tests for integrated web search service."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=IntegratedSearchClient)

    @pytest.fixture
    def service(self, mock_client):
        return IntegratedWebSearchService(
            client=mock_client,
            max_results=3,
            model_type="big",
        )

    @pytest.mark.asyncio
    async def test_search_builds_correct_request(self, service, mock_client):
        """Test that search builds the correct request body."""
        mock_client.search.return_value = {
            "web_search_results": [
                {"title": "Test", "url": "https://test.com", "snippet": "A test result"},
            ]
        }

        results = await service.search("test query")

        call_args = mock_client.search.call_args[0][0]
        assert call_args["web_search"] is True
        assert call_args["rag_search"] is False
        assert call_args["llm_task_block_search"] is False
        assert call_args["web_search_params"]["query"] == "test query"
        assert call_args["web_search_params"]["max_results"] == 3
        assert call_args["web_search_params"]["model_type"] == "big"
        assert len(results) == 1
        assert isinstance(results[0], WebSearchResult)

    @pytest.mark.asyncio
    async def test_search_timeout_raises_tool_error(self, service, mock_client):
        """Test that timeouts produce ToolExecutionError."""
        mock_client.search.side_effect = httpx.ReadTimeout("timeout")

        with pytest.raises(ToolExecutionError) as exc_info:
            await service.search("test query")
        assert exc_info.value.tool_name == "web_search"

    @pytest.mark.asyncio
    async def test_search_http_error_raises_tool_error(self, service, mock_client):
        """Test that HTTP errors produce ToolExecutionError."""
        response = MagicMock()
        response.status_code = 500
        mock_client.search.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=response
        )

        with pytest.raises(ToolExecutionError) as exc_info:
            await service.search("test query")
        assert exc_info.value.tool_name == "web_search"

    @pytest.mark.asyncio
    async def test_close_is_noop(self, service):
        """Test that close does not close the shared client."""
        await service.close()  # Should not raise


# --- IntegratedTaskBlockSearchService Tests ---


class TestIntegratedTaskBlockSearchService:
    """Tests for integrated task block search service."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=IntegratedSearchClient)

    @pytest.fixture
    def llm_service(self, mock_client):
        return IntegratedTaskBlockSearchService(
            client=mock_client,
            search_type="llm",
            is_reason_required=True,
        )

    @pytest.fixture
    def elastic_service(self, mock_client):
        return IntegratedTaskBlockSearchService(
            client=mock_client,
            search_type="elastic",
            elastic_size=5,
        )

    @pytest.mark.asyncio
    async def test_llm_search_builds_correct_request(self, llm_service, mock_client):
        """Test LLM search type sets correct flags."""
        mock_client.search.return_value = {
            "llm_task_block_search_results": [
                {
                    "block_id": "export-config",
                    "name": "Export Config",
                    "action_code": "ExportConfigurations",
                    "relevance_score": 0.9,
                },
            ]
        }

        results = await llm_service.search("export config")

        call_args = mock_client.search.call_args[0][0]
        assert call_args["llm_task_block_search"] is True
        assert call_args["plain_elastic_task_block_search"] is False
        assert call_args["web_search"] is False
        assert call_args["llm_task_block_search_params"]["query"] == "export config"
        assert call_args["llm_task_block_search_params"]["is_reason_required"] is True
        assert len(results) == 1
        assert isinstance(results[0], TaskBlockSearchResult)

    @pytest.mark.asyncio
    async def test_elastic_search_builds_correct_request(self, elastic_service, mock_client):
        """Test elastic search type sets correct flags."""
        mock_client.search.return_value = {
            "plain_elastic_task_block_search_results": [
                {
                    "block_id": "import-data",
                    "name": "Import Data",
                    "action_code": "ImportData",
                    "score": 0.8,
                },
            ]
        }

        results = await elastic_service.search("import data")

        call_args = mock_client.search.call_args[0][0]
        assert call_args["plain_elastic_task_block_search"] is True
        assert call_args["llm_task_block_search"] is False
        assert call_args["plain_elastic_task_block_search_params"]["query"] == "import data"
        assert call_args["plain_elastic_task_block_search_params"]["size"] == 5
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_timeout_raises_tool_error(self, llm_service, mock_client):
        """Test that timeouts produce ToolExecutionError."""
        mock_client.search.side_effect = httpx.ReadTimeout("timeout")

        with pytest.raises(ToolExecutionError) as exc_info:
            await llm_service.search("test")
        assert exc_info.value.tool_name == "task_block_search"

    @pytest.mark.asyncio
    async def test_get_block_details_returns_none(self, llm_service):
        """Test get_block_details returns None (unsupported)."""
        result = await llm_service.get_block_details("some-block")
        assert result is None


# --- Factory Routing Tests ---


class TestSearchServiceFactoryRouting:
    """Tests for factory backend routing."""

    def _make_settings(self, **overrides) -> Settings:
        base = {
            "llm_provider": "vllm",
            "llm_base_url": "http://localhost:8000/v1",
            "llm_api_key": "test",
            "llm_model_name": "test-model",
            "redis_url": "",
        }
        base.update(overrides)
        return Settings(**base)

    def test_web_search_perplexity_backend(self):
        """Test factory returns WebSearchService for perplexity backend."""
        from reasoning_engine_pro.services.search.factory import SearchServiceFactory
        from reasoning_engine_pro.services.search.web_search import WebSearchService

        SearchServiceFactory.reset()
        settings = self._make_settings(web_search_backend="perplexity")
        service = SearchServiceFactory.create_web_search(settings)
        assert isinstance(service, WebSearchService)

    def test_web_search_integrated_backend(self):
        """Test factory returns IntegratedWebSearchService for integrated backend."""
        from reasoning_engine_pro.services.search.factory import SearchServiceFactory

        SearchServiceFactory.reset()
        settings = self._make_settings(
            web_search_backend="integrated",
            integrated_search_url="http://test:443/search",
            integrated_search_api_key="pk_test",
        )
        service = SearchServiceFactory.create_web_search(settings)
        assert isinstance(service, IntegratedWebSearchService)
        SearchServiceFactory.reset()

    def test_task_block_legacy_backend(self):
        """Test factory returns TaskBlockSearchService for legacy backend."""
        from reasoning_engine_pro.services.search.factory import SearchServiceFactory
        from reasoning_engine_pro.services.search.task_block import TaskBlockSearchService

        SearchServiceFactory.reset()
        settings = self._make_settings(task_block_search_backend="legacy")
        service = SearchServiceFactory.create_task_block_search(settings)
        assert isinstance(service, TaskBlockSearchService)

    def test_task_block_integrated_backend(self):
        """Test factory returns IntegratedTaskBlockSearchService for integrated backend."""
        from reasoning_engine_pro.services.search.factory import SearchServiceFactory

        SearchServiceFactory.reset()
        settings = self._make_settings(
            task_block_search_backend="integrated",
            integrated_search_url="http://test:443/search",
            integrated_search_api_key="pk_test",
        )
        service = SearchServiceFactory.create_task_block_search(settings)
        assert isinstance(service, IntegratedTaskBlockSearchService)
        SearchServiceFactory.reset()

    def test_shared_client_reused(self):
        """Test that both integrated services share the same client."""
        from reasoning_engine_pro.services.search.factory import SearchServiceFactory

        SearchServiceFactory.reset()
        settings = self._make_settings(
            web_search_backend="integrated",
            task_block_search_backend="integrated",
            integrated_search_url="http://test:443/search",
            integrated_search_api_key="pk_test",
        )
        web_service = SearchServiceFactory.create_web_search(settings)
        tb_service = SearchServiceFactory.create_task_block_search(settings)
        assert web_service._client is tb_service._client
        SearchServiceFactory.reset()
