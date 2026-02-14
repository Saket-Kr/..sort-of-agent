"""Rough token estimation for message lists."""

from ..schemas.messages import ChatMessage


def estimate_tokens(messages: list[ChatMessage]) -> int:
    """Estimate token count. ~4 characters per token, +10 overhead per message."""
    total = sum(len(m.content or "") + len(m.role.value) + 10 for m in messages)
    return max(1, total // 4)


def should_summarize(messages: list[ChatMessage], limit: int = 100_000) -> bool:
    """Check if messages exceed the token limit and should be summarized."""
    return estimate_tokens(messages) > limit
