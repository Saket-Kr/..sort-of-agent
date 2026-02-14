"""Tests for MessageSummarizer and token estimation."""

from unittest.mock import AsyncMock

import pytest

from reasoning_engine_pro.agents.summarizer import MessageSummarizer
from reasoning_engine_pro.core.enums import MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage
from reasoning_engine_pro.core.utils.token_estimation import (
    estimate_tokens,
    should_summarize,
)


# ---------------------------------------------------------------------------
# Token estimation tests
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    """Tests for token estimation utilities."""

    def test_estimate_tokens_single_message(self):
        messages = [ChatMessage(role=MessageRole.USER, content="Hello world")]
        tokens = estimate_tokens(messages)
        # "Hello world" = 11 chars, "user" = 4, +10 overhead = 25 / 4 ~ 6
        assert tokens > 0
        assert tokens < 100

    def test_estimate_tokens_empty_content(self):
        messages = [ChatMessage(role=MessageRole.USER, content="")]
        tokens = estimate_tokens(messages)
        assert tokens >= 1

    def test_estimate_tokens_multiple_messages(self):
        messages = [
            ChatMessage(role=MessageRole.USER, content="Short"),
            ChatMessage(role=MessageRole.ASSISTANT, content="A" * 1000),
        ]
        tokens = estimate_tokens(messages)
        # Second message has ~1000 chars → ~250 tokens + overhead
        assert tokens > 200

    def test_estimate_tokens_none_content(self):
        messages = [ChatMessage(role=MessageRole.USER, content=None)]
        tokens = estimate_tokens(messages)
        assert tokens >= 1

    def test_should_summarize_below_limit(self):
        messages = [ChatMessage(role=MessageRole.USER, content="Hello")]
        assert should_summarize(messages, limit=100_000) is False

    def test_should_summarize_above_limit(self):
        # Create messages totaling well above 100K tokens
        big_content = "x" * 500_000  # ~125K tokens
        messages = [ChatMessage(role=MessageRole.USER, content=big_content)]
        assert should_summarize(messages, limit=100_000) is True

    def test_should_summarize_custom_limit(self):
        messages = [ChatMessage(role=MessageRole.USER, content="x" * 100)]
        # With limit=5, ~25 tokens > 5 → should summarize
        assert should_summarize(messages, limit=5) is True


# ---------------------------------------------------------------------------
# MessageSummarizer tests
# ---------------------------------------------------------------------------


class TestMessageSummarizer:
    """Tests for MessageSummarizer."""

    @pytest.fixture
    def mock_llm(self):
        return AsyncMock()

    @pytest.fixture
    def summarizer(self, mock_llm):
        return MessageSummarizer(llm_provider=mock_llm)

    @pytest.mark.asyncio
    async def test_short_messages_returned_as_is(self, summarizer):
        """Messages with 2 or fewer items are returned unchanged."""
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content="System prompt"),
            ChatMessage(role=MessageRole.USER, content="Hello"),
        ]
        result = await summarizer.summarize(messages)
        assert result == messages

    @pytest.mark.asyncio
    async def test_summarizes_long_conversation(self, summarizer, mock_llm):
        """Conversation with >2 messages is summarized."""
        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content="User wants to export HCM config for Benefits.",
            )
        )

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content="System prompt"),
            ChatMessage(
                role=MessageRole.USER,
                content="Export HCM configuration",
            ),
            ChatMessage(
                role=MessageRole.ASSISTANT,
                content="Which module do you want to export?",
            ),
            ChatMessage(
                role=MessageRole.USER,
                content="Benefits module",
            ),
        ]

        result = await summarizer.summarize(messages)

        # Should have system message + 1 summary message
        assert len(result) == 2
        assert result[0].role == MessageRole.SYSTEM
        assert result[0].content == "System prompt"
        assert result[1].role == MessageRole.USER
        assert "[Conversation Summary]" in result[1].content
        assert "HCM" in result[1].content

    @pytest.mark.asyncio
    async def test_preserves_system_message(self, summarizer, mock_llm):
        """System message is preserved in output."""
        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content="Summary text",
            )
        )

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content="You are a planner"),
            ChatMessage(role=MessageRole.USER, content="Hello"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Hi!"),
            ChatMessage(role=MessageRole.USER, content="Create workflow"),
        ]

        result = await summarizer.summarize(messages)

        assert result[0].role == MessageRole.SYSTEM
        assert result[0].content == "You are a planner"

    @pytest.mark.asyncio
    async def test_no_system_message(self, summarizer, mock_llm):
        """Works when there is no system message."""
        mock_llm.generate = AsyncMock(
            return_value=ChatMessage(
                role=MessageRole.ASSISTANT,
                content="Summary without system",
            )
        )

        messages = [
            ChatMessage(role=MessageRole.USER, content="Hello"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Hi!"),
            ChatMessage(role=MessageRole.USER, content="Create workflow"),
        ]

        result = await summarizer.summarize(messages)

        # No system message in output, just the summary
        assert len(result) == 1
        assert result[0].role == MessageRole.USER
        assert "Summary without system" in result[0].content

    @pytest.mark.asyncio
    async def test_returns_original_on_llm_failure(self, summarizer, mock_llm):
        """Returns original messages when LLM call fails."""
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

        messages = [
            ChatMessage(role=MessageRole.USER, content="Hello"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Hi!"),
            ChatMessage(role=MessageRole.USER, content="Create workflow"),
        ]

        result = await summarizer.summarize(messages)
        assert result == messages

    @pytest.mark.asyncio
    async def test_calls_llm_with_conversation_text(self, summarizer, mock_llm):
        """LLM is called with formatted conversation text."""
        captured_messages = None

        async def capture_generate(messages, **kwargs):
            nonlocal captured_messages
            captured_messages = messages
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content="Summary",
            )

        mock_llm.generate = capture_generate

        messages = [
            ChatMessage(role=MessageRole.USER, content="Export config"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Which module?"),
            ChatMessage(role=MessageRole.USER, content="Benefits"),
        ]

        await summarizer.summarize(messages)

        assert captured_messages is not None
        # Should have system prompt + user message with conversation text
        assert len(captured_messages) == 2
        assert captured_messages[0].role == MessageRole.SYSTEM
        user_content = captured_messages[1].content
        assert "Export config" in user_content
        assert "Which module?" in user_content
        assert "Benefits" in user_content

    @pytest.mark.asyncio
    async def test_uses_low_temperature(self, summarizer, mock_llm):
        """Summarizer uses low temperature for deterministic output."""
        captured_kwargs = {}

        async def capture_generate(messages, **kwargs):
            captured_kwargs.update(kwargs)
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content="Summary",
            )

        mock_llm.generate = capture_generate

        messages = [
            ChatMessage(role=MessageRole.USER, content="A"),
            ChatMessage(role=MessageRole.ASSISTANT, content="B"),
            ChatMessage(role=MessageRole.USER, content="C"),
        ]

        await summarizer.summarize(messages)
        assert captured_kwargs.get("temperature") == 0.1
