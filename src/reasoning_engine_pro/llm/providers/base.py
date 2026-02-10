"""Base LLM provider implementation."""

import json
from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Optional

from openai import AsyncOpenAI

from ...core.enums import MessageRole
from ...core.exceptions import LLMProviderError
from ...core.interfaces.llm_provider import (
    ILLMProvider,
    LLMStreamChunk,
    ToolDefinition,
)
from ...core.schemas.messages import ChatMessage, ToolCall


class BaseLLMProvider(ILLMProvider):
    """Base implementation for OpenAI-compatible LLM providers."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: float = 120.0,
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._model_name = model_name
        self._timeout = timeout
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def supports_function_calling(self) -> bool:
        return True

    def _messages_to_openai(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """Convert ChatMessages to OpenAI format."""
        result = []
        for msg in messages:
            openai_msg: dict[str, Any] = {"role": msg.role.value}

            if msg.content is not None:
                openai_msg["content"] = msg.content

            if msg.tool_calls:
                openai_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                            if isinstance(tc.arguments, dict)
                            else tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id

            if msg.name:
                openai_msg["name"] = msg.name

            result.append(openai_msg)
        return result

    def _tools_to_openai(
        self, tools: Optional[list[ToolDefinition]]
    ) -> Optional[list[dict[str, Any]]]:
        """Convert ToolDefinitions to OpenAI format."""
        if not tools:
            return None
        return [tool.to_openai_format() for tool in tools]

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        response_format: Optional[type] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Generate streaming response."""
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
        """Generate complete response."""
        ...

    def _parse_tool_calls(
        self, tool_calls_data: list[Any]
    ) -> list[ToolCall]:
        """Parse tool calls from OpenAI response."""
        result = []
        for tc in tool_calls_data:
            try:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                result.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )
            except json.JSONDecodeError as e:
                raise LLMProviderError(
                    f"Failed to parse tool call arguments: {e}",
                    {"tool_call": str(tc)},
                )
        return result
