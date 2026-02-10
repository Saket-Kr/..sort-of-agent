"""Direct OpenAI provider implementation."""

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

from openai import APIError

from ...core.enums import MessageRole
from ...core.exceptions import LLMProviderError
from ...core.interfaces.llm_provider import LLMStreamChunk, ToolDefinition
from ...core.schemas.messages import ChatMessage, ToolCall
from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Direct OpenAI API provider."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4-turbo-preview",
        timeout: float = 120.0,
    ):
        super().__init__(
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
        )

    async def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        response_format: Optional[type] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Generate streaming response from OpenAI."""
        try:
            openai_messages = self._messages_to_openai(messages)
            openai_tools = self._tools_to_openai(tools)

            kwargs: dict[str, Any] = {
                "model": self._model_name,
                "messages": openai_messages,
                "temperature": temperature,
                "stream": True,
            }

            if openai_tools:
                kwargs["tools"] = openai_tools
                kwargs["tool_choice"] = "auto"

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            if response_format:
                kwargs["response_format"] = {"type": "json_object"}

            stream = await self._client.chat.completions.create(**kwargs)

            # Accumulate tool calls across chunks
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                if delta is None:
                    continue

                content = delta.content
                tool_calls: list[ToolCall] = []

                # Handle tool calls streaming
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index

                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }

                        if tc_delta.id:
                            accumulated_tool_calls[idx]["id"] = tc_delta.id

                        if tc_delta.function:
                            if tc_delta.function.name:
                                accumulated_tool_calls[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                accumulated_tool_calls[idx][
                                    "arguments"
                                ] += tc_delta.function.arguments

                # On tool_calls finish, parse accumulated calls
                if finish_reason == "tool_calls":
                    for tc_data in accumulated_tool_calls.values():
                        try:
                            args = json.loads(tc_data["arguments"])
                        except json.JSONDecodeError:
                            args = {}
                        tool_calls.append(
                            ToolCall(
                                id=tc_data["id"],
                                name=tc_data["name"],
                                arguments=args,
                            )
                        )

                yield LLMStreamChunk(
                    content=content,
                    tool_calls=tool_calls,
                    finish_reason=finish_reason,
                    is_complete=finish_reason is not None,
                )

        except APIError as e:
            raise LLMProviderError(
                f"OpenAI API error: {e.message}",
                {"status_code": e.status_code, "body": str(e.body)},
            )
        except Exception as e:
            raise LLMProviderError(f"OpenAI error: {str(e)}")

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        response_format: Optional[type] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ChatMessage:
        """Generate complete response from OpenAI."""
        try:
            openai_messages = self._messages_to_openai(messages)
            openai_tools = self._tools_to_openai(tools)

            kwargs: dict[str, Any] = {
                "model": self._model_name,
                "messages": openai_messages,
                "temperature": temperature,
            }

            if openai_tools:
                kwargs["tools"] = openai_tools
                kwargs["tool_choice"] = "auto"

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            if response_format:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            tool_calls = None
            if message.tool_calls:
                tool_calls = self._parse_tool_calls(message.tool_calls)

            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=message.content,
                tool_calls=tool_calls,
            )

        except APIError as e:
            raise LLMProviderError(
                f"OpenAI API error: {e.message}",
                {"status_code": e.status_code, "body": str(e.body)},
            )
        except Exception as e:
            raise LLMProviderError(f"OpenAI error: {str(e)}")
