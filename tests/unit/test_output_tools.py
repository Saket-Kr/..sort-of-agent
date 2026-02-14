"""Tests for output tool schemas, executors, and planner integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from reasoning_engine_pro.core.schemas.tools import (
    PresentAnswerInput,
    PresentAnswerOutput,
    SubmitWorkflowInput,
    SubmitWorkflowOutput,
    ThinkApproachInput,
    ThinkApproachOutput,
)
from reasoning_engine_pro.core.schemas.workflow import Block, Edge
from reasoning_engine_pro.tools.executors.present_answer import PresentAnswerExecutor
from reasoning_engine_pro.tools.executors.submit_workflow import SubmitWorkflowExecutor
from reasoning_engine_pro.tools.executors.think_approach import ThinkApproachExecutor


class TestThinkApproachExecutor:
    """Tests for think_approach tool executor."""

    @pytest.fixture
    def executor(self):
        return ThinkApproachExecutor()

    def test_tool_name(self, executor):
        assert executor.tool_name == "think_approach"

    @pytest.mark.asyncio
    async def test_returns_acknowledged(self, executor):
        result = await executor.execute(
            ThinkApproachInput(summary="Analyzing the request")
        )
        assert isinstance(result, ThinkApproachOutput)
        assert result.acknowledged is True

    def test_to_openai_function(self, executor):
        func = executor.to_openai_function()
        assert func["function"]["name"] == "think_approach"
        assert "summary" in func["function"]["parameters"]["properties"]


class TestPresentAnswerExecutor:
    """Tests for present_answer tool executor."""

    @pytest.fixture
    def executor(self):
        return PresentAnswerExecutor()

    def test_tool_name(self, executor):
        assert executor.tool_name == "present_answer"

    @pytest.mark.asyncio
    async def test_returns_delivered(self, executor):
        result = await executor.execute(
            PresentAnswerInput(content="Here is your workflow...")
        )
        assert isinstance(result, PresentAnswerOutput)
        assert result.delivered is True


class TestSubmitWorkflowExecutor:
    """Tests for submit_workflow tool executor."""

    @pytest.fixture
    def executor(self):
        return SubmitWorkflowExecutor()

    def test_tool_name(self, executor):
        assert executor.tool_name == "submit_workflow"

    @pytest.mark.asyncio
    async def test_valid_workflow_accepted(self, executor):
        result = await executor.execute(
            SubmitWorkflowInput(
                workflow_json=[
                    {
                        "BlockId": "B001",
                        "Name": "Start",
                        "ActionCode": "Start",
                        "Inputs": [],
                        "Outputs": [],
                    },
                    {
                        "BlockId": "B002",
                        "Name": "Export",
                        "ActionCode": "ExportConfigurations",
                        "Inputs": [],
                        "Outputs": [],
                    },
                ],
                edges=[
                    {"EdgeID": "E001", "From": "B001", "To": "B002"},
                ],
            )
        )
        assert isinstance(result, SubmitWorkflowOutput)
        assert result.status == "accepted"
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_missing_start_block_rejected(self, executor):
        result = await executor.execute(
            SubmitWorkflowInput(
                workflow_json=[
                    {
                        "BlockId": "B002",
                        "Name": "Export",
                        "ActionCode": "ExportConfigurations",
                        "Inputs": [],
                        "Outputs": [],
                    },
                ],
                edges=[],
            )
        )
        assert result.status == "needs_revision"
        assert len(result.errors) > 0
        assert any("Start" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_invalid_edge_reference_rejected(self, executor):
        result = await executor.execute(
            SubmitWorkflowInput(
                workflow_json=[
                    {
                        "BlockId": "B001",
                        "Name": "Start",
                        "ActionCode": "Start",
                        "Inputs": [],
                        "Outputs": [],
                    },
                ],
                edges=[
                    {"EdgeID": "E001", "From": "B001", "To": "B999"},
                ],
            )
        )
        assert result.status == "needs_revision"
        assert any("B999" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_invalid_json_structure_rejected(self, executor):
        result = await executor.execute(
            SubmitWorkflowInput(
                workflow_json=[
                    {"invalid": "block"},  # Missing required fields
                ],
                edges=[],
            )
        )
        assert result.status == "needs_revision"
        assert len(result.errors) > 0


class TestToolDefinitions:
    """Tests for tool definitions list."""

    def test_all_six_tools_registered(self):
        from reasoning_engine_pro.tools.definitions import TOOL_DEFINITIONS

        names = [t.name for t in TOOL_DEFINITIONS]
        assert "web_search" in names
        assert "task_block_search" in names
        assert "clarify" in names
        assert "think_approach" in names
        assert "present_answer" in names
        assert "submit_workflow" in names

    def test_total_count(self):
        from reasoning_engine_pro.tools.definitions import TOOL_DEFINITIONS

        assert len(TOOL_DEFINITIONS) == 6


class TestToolFactory:
    """Tests for tool factory registration of output tools."""

    def test_factory_registers_output_tools(self, test_settings):
        from reasoning_engine_pro.tools.factory import ToolFactory
        from reasoning_engine_pro.tools.registry import ToolRegistry

        ToolRegistry.reset()
        registry = ToolFactory.create_all(test_settings)

        assert registry.get("think_approach") is not None
        assert registry.get("present_answer") is not None
        assert registry.get("submit_workflow") is not None

        ToolRegistry.reset()
