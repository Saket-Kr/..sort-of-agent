"""Integration tests for Redis storage."""

import pytest
from unittest.mock import AsyncMock, patch

from reasoning_engine_pro.core.enums import ConversationStatus, MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage, ConversationState
from reasoning_engine_pro.services.storage.redis import RedisStorage


class TestRedisStorage:
    """Integration tests for RedisStorage.

    Note: These tests use fakeredis for testing without a real Redis instance.
    """

    @pytest.fixture
    async def storage(self):
        """Create Redis storage with fakeredis."""
        # Use fakeredis for testing
        import fakeredis.aioredis

        storage = RedisStorage(
            redis_url="redis://localhost:6379",
            default_ttl=3600,
        )
        # Replace client with fakeredis
        storage._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield storage
        await storage.disconnect()

    @pytest.mark.asyncio
    async def test_save_and_get_message(self, storage):
        """Test saving and retrieving messages."""
        msg = ChatMessage(role=MessageRole.USER, content="Test message")

        # Save
        result = await storage.save_message("conv-123", msg)
        assert result is True

        # Get
        history = await storage.get_history("conv-123")
        assert len(history) == 1
        assert history[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_save_and_get_state(self, storage):
        """Test saving and retrieving conversation state."""
        state = ConversationState(
            conversation_id="conv-123",
            status=ConversationStatus.ACTIVE,
        )

        # Save
        result = await storage.save_state("conv-123", state)
        assert result is True

        # Get
        retrieved = await storage.get_state("conv-123")
        assert retrieved is not None
        assert retrieved.conversation_id == "conv-123"
        assert retrieved.status == ConversationStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_save_and_get_draft(self, storage):
        """Test saving and retrieving draft."""
        # Save
        result = await storage.save_draft("conv-123", "Draft content")
        assert result is True

        # Get
        draft = await storage.get_draft("conv-123")
        assert draft == "Draft content"

    @pytest.mark.asyncio
    async def test_exists(self, storage):
        """Test checking conversation existence."""
        # Not exists
        assert await storage.exists("conv-123") is False

        # Create
        state = ConversationState(
            conversation_id="conv-123",
            status=ConversationStatus.ACTIVE,
        )
        await storage.save_state("conv-123", state)

        # Exists
        assert await storage.exists("conv-123") is True

    @pytest.mark.asyncio
    async def test_delete_conversation(self, storage):
        """Test deleting conversation."""
        # Setup
        state = ConversationState(
            conversation_id="conv-123",
            status=ConversationStatus.ACTIVE,
        )
        await storage.save_state("conv-123", state)
        await storage.save_draft("conv-123", "Draft")

        # Verify exists
        assert await storage.exists("conv-123") is True

        # Delete
        result = await storage.delete_conversation("conv-123")
        assert result is True

        # Verify deleted
        assert await storage.exists("conv-123") is False
        assert await storage.get_draft("conv-123") is None

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, storage):
        """Test retrieving limited message history."""
        # Save multiple messages
        for i in range(5):
            msg = ChatMessage(role=MessageRole.USER, content=f"Message {i}")
            await storage.save_message("conv-123", msg)

        # Get with limit
        history = await storage.get_history("conv-123", max_messages=3)

        assert len(history) == 3
        # Should get last 3 messages
        assert history[0].content == "Message 2"
        assert history[2].content == "Message 4"

    @pytest.mark.asyncio
    async def test_clarification_flow(self, storage):
        """Test clarification request/response flow."""
        conv_id = "conv-123"
        clarify_id = "clarify-456"

        # Save request
        await storage.save_clarification_request(
            conv_id, clarify_id, ["Question 1", "Question 2"]
        )

        # No response yet
        response = await storage.get_clarification_response(conv_id, clarify_id)
        assert response is None

        # Save response
        await storage.save_clarification_response(
            conv_id, clarify_id, "User response"
        )

        # Get response
        response = await storage.get_clarification_response(conv_id, clarify_id)
        assert response == "User response"
