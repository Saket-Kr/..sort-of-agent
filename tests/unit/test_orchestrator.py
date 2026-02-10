"""Tests for ConversationOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from reasoning_engine_pro.agents.orchestrator import ConversationOrchestrator
from reasoning_engine_pro.agents.few_shot import FewShotRetriever
from reasoning_engine_pro.agents.job_name import JobNameGenerator
from reasoning_engine_pro.agents.planner import PlannerAgent
from reasoning_engine_pro.agents.validator import WorkflowValidator
from reasoning_engine_pro.core.enums import ConversationStatus, MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage, ConversationState
from reasoning_engine_pro.services.storage.memory import InMemoryStorage


class TestConversationOrchestrator:
    """Tests for ConversationOrchestrator."""

    @pytest.fixture
    def mock_planner(self):
        """Create mock planner."""
        planner = AsyncMock(spec=PlannerAgent)
        planner.plan = AsyncMock(return_value=("Test response", None))
        return planner

    @pytest.fixture
    def mock_validator(self):
        """Create mock validator."""
        return MagicMock(spec=WorkflowValidator)

    @pytest.fixture
    def mock_event_emitter(self):
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        emitter.emit_stream_chunk = AsyncMock()
        emitter.emit_error = AsyncMock()
        return emitter

    @pytest.fixture
    def orchestrator(
        self,
        memory_storage,
        mock_planner,
        mock_validator,
        mock_event_emitter,
    ):
        """Create orchestrator with mocks."""
        return ConversationOrchestrator(
            storage=memory_storage,
            planner=mock_planner,
            validator=mock_validator,
            job_name_generator=JobNameGenerator(),
            few_shot_retriever=FewShotRetriever(),
            event_emitter=mock_event_emitter,
        )

    @pytest.mark.asyncio
    async def test_start_conversation(
        self, orchestrator, memory_storage, mock_event_emitter
    ):
        """Test starting a new conversation."""
        await orchestrator.start_conversation(
            conversation_id="test-123",
            initial_message="Create a workflow",
        )

        # Check state was saved
        state = await memory_storage.get_state("test-123")
        assert state is not None
        assert state.conversation_id == "test-123"

        # Check message was saved
        history = await memory_storage.get_history("test-123")
        assert len(history) >= 1
        assert history[0].content == "Create a workflow"

    @pytest.mark.asyncio
    async def test_get_conversation_state(self, orchestrator, memory_storage):
        """Test getting conversation state."""
        # Setup state
        state = ConversationState(
            conversation_id="test-123",
            status=ConversationStatus.ACTIVE,
        )
        await memory_storage.save_state("test-123", state)

        # Get state
        result = await orchestrator.get_conversation_state("test-123")

        assert result is not None
        assert result.conversation_id == "test-123"

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, orchestrator, memory_storage):
        """Test getting conversation history."""
        # Setup messages
        msg = ChatMessage(role=MessageRole.USER, content="Test message")
        await memory_storage.save_message("test-123", msg)

        # Get history
        history = await orchestrator.get_conversation_history("test-123")

        assert len(history) == 1
        assert history[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_end_conversation(self, orchestrator, memory_storage):
        """Test ending a conversation."""
        # Setup state
        state = ConversationState(
            conversation_id="test-123",
            status=ConversationStatus.ACTIVE,
        )
        await memory_storage.save_state("test-123", state)

        # End conversation
        await orchestrator.end_conversation("test-123")

        # Check status updated
        result = await memory_storage.get_state("test-123")
        assert result.status == ConversationStatus.COMPLETED
