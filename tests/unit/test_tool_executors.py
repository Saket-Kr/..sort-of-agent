"""Tests for tool executors."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from reasoning_engine_pro.core.schemas.tools import (
    ClarifyInput,
    ClarifyOutput,
    TaskBlockSearchInput,
    TaskBlockSearchResult,
    WebSearchInput,
    WebSearchResult,
)
from reasoning_engine_pro.tools.executors.clarify import ClarifyExecutor
from reasoning_engine_pro.tools.executors.task_block_search import TaskBlockSearchExecutor
from reasoning_engine_pro.tools.executors.web_search import WebSearchExecutor


@pytest.fixture
def mock_web_search_service():
    """Create mock web search service."""
    service = AsyncMock()
    service.search = AsyncMock(
        return_value=[
            WebSearchResult(
                title="Test Result",
                url="https://example.com",
                snippet="Test snippet",
            )
        ]
    )
    return service


@pytest.fixture
def mock_task_block_search_service():
    """Create mock task block search service."""
    service = AsyncMock()
    service.search = AsyncMock(
        return_value=[
            TaskBlockSearchResult(
                block_id="export-config",
                name="Export Configuration",
                action_code="ExportConfigurations",
                relevance_score=0.9,
            )
        ]
    )
    return service


class TestClarifyExecutor:
    """Tests for ClarifyExecutor."""

    def test_tool_name(self):
        """Test tool name."""
        executor = ClarifyExecutor()
        assert executor.tool_name == "clarify"

    def test_requires_user_response(self):
        """Test requires_user_response flag."""
        executor = ClarifyExecutor()
        assert executor.requires_user_response is True

    @pytest.mark.asyncio
    async def test_execute(self):
        """Test execute returns clarification output."""
        executor = ClarifyExecutor()
        input_data = ClarifyInput(questions=["What module?", "What format?"])

        result = await executor.execute(input_data)

        assert isinstance(result, ClarifyOutput)
        assert result.clarification_id is not None
        assert result.questions == ["What module?", "What format?"]
        assert result.status == "awaiting_response"

    def test_to_openai_function(self):
        """Test OpenAI function format."""
        executor = ClarifyExecutor()
        func = executor.to_openai_function()

        assert func["type"] == "function"
        assert func["function"]["name"] == "clarify"
        assert "parameters" in func["function"]


class TestWebSearchExecutor:
    """Tests for WebSearchExecutor."""

    def test_tool_name(self, mock_web_search_service):
        """Test tool name."""
        executor = WebSearchExecutor(mock_web_search_service)
        assert executor.tool_name == "web_search"

    def test_requires_user_response(self, mock_web_search_service):
        """Test requires_user_response flag."""
        executor = WebSearchExecutor(mock_web_search_service)
        assert executor.requires_user_response is False

    @pytest.mark.asyncio
    async def test_execute(self, mock_web_search_service):
        """Test execute performs searches."""
        executor = WebSearchExecutor(mock_web_search_service)
        input_data = WebSearchInput(queries=["query1", "query2"])

        result = await executor.execute(input_data)

        assert result.query_count == 2
        assert mock_web_search_service.search.call_count == 2


class TestTaskBlockSearchExecutor:
    """Tests for TaskBlockSearchExecutor."""

    def test_tool_name(self, mock_task_block_search_service):
        """Test tool name."""
        executor = TaskBlockSearchExecutor(mock_task_block_search_service)
        assert executor.tool_name == "task_block_search"

    @pytest.mark.asyncio
    async def test_execute_deduplicates(self, mock_task_block_search_service):
        """Test execute deduplicates results by block_id."""
        executor = TaskBlockSearchExecutor(mock_task_block_search_service)
        input_data = TaskBlockSearchInput(queries=["export", "config"])

        result = await executor.execute(input_data)

        # Should have 1 unique result, not 2
        assert len(result.results) == 1
        assert result.query_count == 2
