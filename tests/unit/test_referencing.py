"""Tests for ReferencingAgent."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from reasoning_engine_pro.agents.referencing import ReferencingAgent
from reasoning_engine_pro.core.enums import EventType, MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage
from reasoning_engine_pro.core.schemas.workflow import Block, Edge, Workflow


def _make_workflow(**overrides) -> Workflow:
    """Create a minimal test workflow."""
    defaults = {
        "workflow_json": [
            Block(
                BlockId="B001",
                ActionCode="Start",
                Name="Start",
            ),
            Block(
                BlockId="B002",
                ActionCode="ExportConfigurations",
                Name="Export Config",
                Inputs=[
                    {
                        "Name": "Environment",
                        "IsMandatory": True,
                        "StaticValue": None,
                    },
                    {
                        "Name": "Module",
                        "IsMandatory": True,
                        "StaticValue": None,
                    },
                ],
            ),
        ],
        "edges": [
            Edge(EdgeID="E001", From="B001", To="B002"),
        ],
    }
    defaults.update(overrides)
    return Workflow(**defaults)


def _make_history() -> list[ChatMessage]:
    return [
        ChatMessage(
            role=MessageRole.USER,
            content="Export HCM configuration for Benefits module",
        ),
        ChatMessage(
            role=MessageRole.ASSISTANT,
            content="I'll create a workflow to export HCM Benefits configuration.",
        ),
    ]


class TestReferencingAgent:
    """Tests for ReferencingAgent."""

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        return llm

    @pytest.fixture
    def mock_emitter(self):
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def agent(self, mock_llm, mock_emitter):
        return ReferencingAgent(
            llm_provider=mock_llm,
            event_emitter=mock_emitter,
        )

    @pytest.mark.asyncio
    async def test_fills_inputs_from_llm_response(self, agent, mock_llm):
        """LLM response with filled inputs is parsed and returned."""
        workflow = _make_workflow()

        # Build expected filled workflow
        filled = workflow.model_dump()
        filled["workflow_json"][1]["Inputs"][0]["StaticValue"] = "HCM"
        filled["workflow_json"][1]["Inputs"][1]["StaticValue"] = "Benefits"

        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content=f"```json\n{json.dumps(filled)}\n```",
            )
        )

        result = await agent.run(
            workflow=workflow,
            history=_make_history(),
            conversation_id="conv-1",
        )

        assert result is not None
        export_block = result.workflow_json[1]
        assert export_block.Inputs[0].StaticValue == "HCM"
        assert export_block.Inputs[1].StaticValue == "Benefits"

    @pytest.mark.asyncio
    async def test_returns_original_on_parse_failure(self, agent, mock_llm):
        """Returns original workflow when LLM response is unparseable."""
        workflow = _make_workflow()

        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content="I cannot parse this workflow correctly.",
            )
        )

        result = await agent.run(
            workflow=workflow,
            history=_make_history(),
            conversation_id="conv-1",
        )

        # Should return the original workflow unchanged
        assert result is workflow

    @pytest.mark.asyncio
    async def test_returns_original_on_llm_exception(self, agent, mock_llm):
        """Returns original workflow when LLM raises an exception."""
        workflow = _make_workflow()

        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

        result = await agent.run(
            workflow=workflow,
            history=_make_history(),
            conversation_id="conv-1",
        )

        assert result is workflow

    @pytest.mark.asyncio
    async def test_emits_referencing_started_event(
        self, agent, mock_llm, mock_emitter
    ):
        """Emits REFERENCING_STARTED event when conversation_id is provided."""
        workflow = _make_workflow()
        filled = workflow.model_dump()
        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content=f"```json\n{json.dumps(filled)}\n```",
            )
        )

        await agent.run(
            workflow=workflow,
            history=_make_history(),
            conversation_id="conv-1",
        )

        mock_emitter.emit.assert_called_once()
        call_args = mock_emitter.emit.call_args
        assert call_args[0][0] == EventType.REFERENCING_STARTED
        assert call_args[0][1]["chat_id"] == "conv-1"

    @pytest.mark.asyncio
    async def test_no_event_without_conversation_id(
        self, agent, mock_llm, mock_emitter
    ):
        """Does not emit event when no conversation_id is provided."""
        workflow = _make_workflow()
        filled = workflow.model_dump()
        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content=f"```json\n{json.dumps(filled)}\n```",
            )
        )

        await agent.run(
            workflow=workflow,
            history=_make_history(),
        )

        mock_emitter.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_builds_query_from_both_roles(self, agent, mock_llm):
        """User and assistant messages are included in query history."""
        workflow = _make_workflow()
        filled = workflow.model_dump()

        captured_prompt = None

        async def capture_generate(messages, **kwargs):
            nonlocal captured_prompt
            captured_prompt = messages[0].content
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=f"```json\n{json.dumps(filled)}\n```",
            )

        mock_llm.generate = capture_generate

        history = _make_history()
        await agent.run(workflow=workflow, history=history)

        assert captured_prompt is not None
        assert "User:" in captured_prompt
        assert "Assistant:" in captured_prompt
        assert "HCM" in captured_prompt

    @pytest.mark.asyncio
    async def test_parses_raw_json_without_fences(self, agent, mock_llm):
        """Parses workflow from raw JSON (no code fences)."""
        workflow = _make_workflow()
        filled = workflow.model_dump()
        filled["workflow_json"][1]["Inputs"][0]["StaticValue"] = "Filled"

        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content=json.dumps(filled),
            )
        )

        result = await agent.run(
            workflow=workflow,
            history=_make_history(),
        )

        assert result.workflow_json[1].Inputs[0].StaticValue == "Filled"


class TestReferencingAgentNoEmitter:
    """Tests with no event emitter configured."""

    @pytest.mark.asyncio
    async def test_works_without_emitter(self):
        """Agent works when no event emitter is provided."""
        mock_llm = AsyncMock()
        agent = ReferencingAgent(llm_provider=mock_llm, event_emitter=None)

        workflow = _make_workflow()
        filled = workflow.model_dump()
        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content=f"```json\n{json.dumps(filled)}\n```",
            )
        )

        result = await agent.run(
            workflow=workflow,
            history=_make_history(),
            conversation_id="conv-1",
        )

        assert result is not None
