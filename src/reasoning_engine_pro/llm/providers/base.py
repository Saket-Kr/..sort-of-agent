"""Base LLM provider implementation."""

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx
from openai import APIError, AsyncOpenAI

from ...core.enums import MessageRole
from ...core.exceptions import LLMProviderError
from ...core.interfaces.llm_provider import ILLMProvider, LLMStreamChunk, ToolDefinition
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

    @property
    def _provider_name(self) -> str:
        """Provider name used in error messages. Override in subclasses."""
        return self.__class__.__name__

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
                            "arguments": (
                                json.dumps(tc.arguments)
                                if isinstance(tc.arguments, dict)
                                else tc.arguments
                            ),
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

    def _build_completion_kwargs(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]],
        response_format: Optional[type],
        temperature: float,
        max_tokens: Optional[int],
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build kwargs dict for the chat completions API call."""
        openai_messages = self._messages_to_openai(messages)
        openai_tools = self._tools_to_openai(tools)

        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": openai_messages,
            "temperature": temperature,
        }

        if stream:
            kwargs["stream"] = True

        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        if response_format:
            kwargs["response_format"] = {"type": "json_object"}

        return kwargs

    async def generate_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        response_format: Optional[type] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Generate streaming response."""
        try:
            kwargs = self._build_completion_kwargs(
                messages, tools, response_format, temperature, max_tokens, stream=True
            )
            stream = await self._client.chat.completions.create(**kwargs)

            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                finish_reason = (
                    chunk.choices[0].finish_reason if chunk.choices else None
                )

                if delta is None:
                    continue

                content = delta.content
                tool_calls: list[ToolCall] = []

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
                                accumulated_tool_calls[idx][
                                    "name"
                                ] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                accumulated_tool_calls[idx][
                                    "arguments"
                                ] += tc_delta.function.arguments

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
                f"{self._provider_name} API error: {e.message}",
                {"status_code": e.status_code, "body": str(e.body)},
            )
        except LLMProviderError:
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise LLMProviderError(f"{self._provider_name} error: {str(e)}")

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        response_format: Optional[type] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ChatMessage:
        """Generate complete response."""
        try:
            kwargs = self._build_completion_kwargs(
                messages, tools, response_format, temperature, max_tokens
            )
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
                f"{self._provider_name} API error: {e.message}",
                {"status_code": e.status_code, "body": str(e.body)},
            )
        except LLMProviderError:
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise LLMProviderError(f"{self._provider_name} error: {str(e)}")

    def _parse_tool_calls(self, tool_calls_data: list[Any]) -> list[ToolCall]:
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
