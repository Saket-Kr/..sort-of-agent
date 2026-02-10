"""LLM Provider interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

from ..schemas.messages import ChatMessage, ToolCall


@dataclass
class ToolDefinition:
    """Definition of a tool for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class LLMStreamChunk:
    """A chunk from LLM streaming response."""

    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    is_complete: bool = False

    @property
    def has_tool_calls(self) -> bool:
        """Check if chunk contains tool calls."""
        return len(self.tool_calls) > 0


class ILLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        response_format: Optional[type] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Generate a streaming response from the LLM.

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions for function calling
            response_format: Optional Pydantic model for structured output
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            LLMStreamChunk objects containing content or tool calls
        """
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        response_format: Optional[type] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ChatMessage:
        """
        Generate a complete response from the LLM (non-streaming).

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions for function calling
            response_format: Optional Pydantic model for structured output
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Complete ChatMessage response
        """
        ...

    @property
    @abstractmethod
    def supports_function_calling(self) -> bool:
        """Check if provider supports native function calling."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name."""
        ...
