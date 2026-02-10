"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from reasoning_engine_pro.core.enums import ConversationStatus, MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage, ConversationState
from reasoning_engine_pro.core.schemas.tools import (
    ClarifyInput,
    TaskBlockSearchInput,
    WebSearchInput,
)
from reasoning_engine_pro.core.schemas.workflow import (
    Block,
    Edge,
    Input,
    Output,
    Workflow,
)


class TestWorkflowSchemas:
    """Tests for workflow schemas."""

    def test_input_with_static_value(self):
        """Test Input with static value."""
        inp = Input(Name="test", StaticValue="value")
        assert inp.Name == "test"
        assert inp.StaticValue == "value"
        assert inp.ReferencedOutputVariableName is None

    def test_input_with_reference(self):
        """Test Input with output reference."""
        inp = Input(Name="test", ReferencedOutputVariableName="op-B001-File")
        assert inp.Name == "test"
        assert inp.ReferencedOutputVariableName == "op-B001-File"

    def test_output_creation(self):
        """Test Output creation."""
        out = Output(Name="Result", OutputVariableName="op-B001-Result")
        assert out.Name == "Result"
        assert out.OutputVariableName == "op-B001-Result"

    def test_block_creation(self):
        """Test Block creation."""
        block = Block(
            BlockId="B001",
            Name="Test Block",
            ActionCode="TestAction",
            Inputs=[Input(Name="in1", StaticValue="val")],
            Outputs=[Output(Name="out1", OutputVariableName="op-B001-out1")],
        )
        assert block.BlockId == "B001"
        assert block.Name == "Test Block"
        assert len(block.Inputs) == 1
        assert len(block.Outputs) == 1

    def test_edge_creation(self):
        """Test Edge creation."""
        edge = Edge(EdgeID="E001", From="B001", To="B002")
        assert edge.EdgeID == "E001"
        assert edge.From == "B001"
        assert edge.To == "B002"
        assert edge.EdgeCondition is None

    def test_edge_with_condition(self):
        """Test Edge with condition."""
        edge = Edge(EdgeID="E001", From="B001", To="B002", EdgeCondition="true")
        assert edge.EdgeCondition == "true"

    def test_workflow_creation(self):
        """Test Workflow creation."""
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="End", ActionCode="End"),
            ],
            edges=[Edge(EdgeID="E001", From="B001", To="B002")],
        )
        assert len(workflow.workflow_json) == 2
        assert len(workflow.edges) == 1

    def test_workflow_get_block_by_id(self):
        """Test getting block by ID."""
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="End", ActionCode="End"),
            ],
            edges=[],
        )
        block = workflow.get_block_by_id("B001")
        assert block is not None
        assert block.Name == "Start"

        assert workflow.get_block_by_id("B999") is None

    def test_workflow_get_start_block(self):
        """Test getting start block."""
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="Process", ActionCode="Process"),
            ],
            edges=[],
        )
        start = workflow.get_start_block()
        assert start is not None
        assert start.BlockId == "B001"

    def test_workflow_validate_structure(self):
        """Test workflow structure validation."""
        # Valid workflow
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="End", ActionCode="End"),
            ],
            edges=[Edge(EdgeID="E001", From="B001", To="B002")],
        )
        errors = workflow.validate_structure()
        assert len(errors) == 0

    def test_workflow_validate_missing_start(self):
        """Test validation catches missing start block."""
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Process", ActionCode="Process"),
            ],
            edges=[],
        )
        errors = workflow.validate_structure()
        assert any("Start block" in e for e in errors)

    def test_workflow_validate_invalid_edge_reference(self):
        """Test validation catches invalid edge references."""
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
            ],
            edges=[Edge(EdgeID="E001", From="B001", To="B999")],
        )
        errors = workflow.validate_structure()
        assert any("B999" in e for e in errors)


class TestMessageSchemas:
    """Tests for message schemas."""

    def test_chat_message_user(self):
        """Test user message creation."""
        msg = ChatMessage(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_chat_message_to_openai_format(self):
        """Test conversion to OpenAI format."""
        msg = ChatMessage(role=MessageRole.USER, content="Hello")
        openai_msg = msg.to_openai_format()
        assert openai_msg["role"] == "user"
        assert openai_msg["content"] == "Hello"

    def test_conversation_state_creation(self):
        """Test conversation state creation."""
        state = ConversationState(
            conversation_id="test-123",
            status=ConversationStatus.ACTIVE,
        )
        assert state.conversation_id == "test-123"
        assert state.status == ConversationStatus.ACTIVE


class TestToolSchemas:
    """Tests for tool schemas."""

    def test_web_search_input_valid(self):
        """Test valid web search input."""
        inp = WebSearchInput(queries=["query1", "query2"])
        assert len(inp.queries) == 2

    def test_web_search_input_too_many_queries(self):
        """Test web search input with too many queries."""
        with pytest.raises(ValidationError):
            WebSearchInput(queries=["q"] * 11)  # Max is 10

    def test_web_search_input_empty_queries(self):
        """Test web search input with empty queries."""
        with pytest.raises(ValidationError):
            WebSearchInput(queries=[])

    def test_task_block_search_input(self):
        """Test task block search input."""
        inp = TaskBlockSearchInput(queries=["export config"])
        assert inp.queries == ["export config"]

    def test_clarify_input_valid(self):
        """Test valid clarify input."""
        inp = ClarifyInput(questions=["What module?", "What format?"])
        assert len(inp.questions) == 2

    def test_clarify_input_too_many_questions(self):
        """Test clarify input with too many questions."""
        with pytest.raises(ValidationError):
            ClarifyInput(questions=["q"] * 6)  # Max is 5
