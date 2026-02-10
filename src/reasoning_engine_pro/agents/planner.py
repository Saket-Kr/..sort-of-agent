"""Planner Agent - main LLM-based planning logic."""

import json
import re
from typing import Any, Optional

from pydantic import ValidationError

from ..core.enums import EventType, MessageRole
from ..core.exceptions import ClarificationRequiredError, WorkflowParseError
from ..observability.logger import get_logger

logger = get_logger(__name__)
from ..core.interfaces.event_emitter import IEventEmitter
from ..core.interfaces.llm_provider import ILLMProvider, ToolDefinition
from ..core.schemas.messages import ChatMessage, ToolCall
from ..core.schemas.tools import ClarifyOutput
from ..core.schemas.workflow import Workflow
from ..tools.definitions import TOOL_DEFINITIONS
from ..tools.registry import ToolRegistry
from .prompts.planner import get_planner_system_prompt


class PlannerAgent:
    """LLM-based planner agent for workflow generation."""

    DEFAULT_MAX_ITERATIONS = 10

    def __init__(
        self,
        llm_provider: ILLMProvider,
        tool_registry: ToolRegistry,
        event_emitter: Optional[IEventEmitter] = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ):
        """
        Initialize planner agent.

        Args:
            llm_provider: LLM provider for generation
            tool_registry: Registry of available tools
            event_emitter: Optional event emitter for progress updates
            max_iterations: Maximum tool call iterations before stopping
        """
        self._llm = llm_provider
        self._tools = tool_registry
        self._event_emitter = event_emitter
        self._max_iterations = max_iterations

    def _get_tool_definitions(self) -> list[ToolDefinition]:
        """Get tool definitions for LLM."""
        return TOOL_DEFINITIONS

    async def plan(
        self,
        conversation_id: str,
        messages: list[ChatMessage],
        user_info: Optional[dict] = None,
        few_shot_examples: Optional[str] = None,
    ) -> tuple[str, Optional[Workflow]]:
        """
        Execute planning loop.

        Args:
            conversation_id: Conversation identifier
            messages: Conversation history
            user_info: Optional user context
            few_shot_examples: Optional few-shot examples

        Returns:
            Tuple of (response_text, optional_workflow)

        Raises:
            ClarificationRequiredError: When clarification is needed
        """
        logger.info(
            "Starting planning",
            conversation_id=conversation_id,
            message_count=len(messages),
        )

        # Build system prompt
        system_prompt = get_planner_system_prompt(user_info, few_shot_examples)
        system_message = ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)

        # Prepare messages with system prompt
        full_messages = [system_message] + messages
        tools = self._get_tool_definitions()

        accumulated_response = ""
        iteration = 0

        while iteration < self._max_iterations:
            iteration += 1
            logger.info(
                "LLM iteration",
                conversation_id=conversation_id,
                iteration=iteration,
            )

            # Stream LLM response
            tool_calls: list[ToolCall] = []
            response_content = ""

            async for chunk in self._llm.generate_stream(
                messages=full_messages,
                tools=tools,
                temperature=0.7,
            ):
                # Handle content streaming
                if chunk.content:
                    response_content += chunk.content
                    accumulated_response += chunk.content

                    # Emit stream chunk
                    if self._event_emitter:
                        await self._event_emitter.emit_stream_chunk(
                            conversation_id, chunk.content
                        )

                # Collect tool calls
                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)

            # If no tool calls, we're done
            if not tool_calls:
                # Try to parse workflow from response
                workflow = self._try_parse_workflow(accumulated_response)
                return accumulated_response, workflow

            # Process tool calls
            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response_content if response_content else None,
                tool_calls=tool_calls,
            )
            full_messages.append(assistant_message)

            # Execute tools and collect results
            for tool_call in tool_calls:
                result = await self._execute_tool(conversation_id, tool_call)

                # Check for clarification
                if isinstance(result, ClarifyOutput):
                    raise ClarificationRequiredError(
                        result.clarification_id, result.questions
                    )

                # Add tool result to messages
                tool_message = ChatMessage(
                    role=MessageRole.TOOL,
                    content=(
                        json.dumps(result)
                        if isinstance(result, dict)
                        else result.model_dump_json()
                    ),
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                )
                full_messages.append(tool_message)

        # Max iterations reached
        workflow = self._try_parse_workflow(accumulated_response)
        return accumulated_response, workflow

    async def _execute_tool(self, conversation_id: str, tool_call: ToolCall) -> Any:
        """Execute a tool call."""
        executor = self._tools.get(tool_call.name)
        if not executor:
            return {"error": f"Unknown tool: {tool_call.name}"}

        # Emit tool started event
        if self._event_emitter:
            event_type = self._get_tool_started_event(tool_call.name)
            await self._event_emitter.emit_tool_started(
                conversation_id, tool_call.name, event_type
            )

        try:
            # Validate and execute
            validated_input = executor.validate_input(tool_call.arguments)
            result = await executor.execute(validated_input)

            # Emit results event
            if self._event_emitter:
                event_type = self._get_tool_results_event(tool_call.name)
                if event_type:
                    result_dict = result.model_dump()
                    await self._event_emitter.emit_tool_results(
                        conversation_id,
                        event_type,
                        result_dict.get("results", []),
                        result_dict.get("query_count", 0),
                        result_dict.get("total_results", 0),
                    )

            return result

        except Exception as e:
            return {"error": str(e)}

    def _get_tool_started_event(self, tool_name: str) -> EventType:
        """Get event type for tool started."""
        mapping = {
            "web_search": EventType.WEB_SEARCH_STARTED,
            "task_block_search": EventType.TASK_BLOCK_SEARCH_STARTED,
        }
        return mapping.get(tool_name, EventType.PROCESSING_STARTED)

    def _get_tool_results_event(self, tool_name: str) -> Optional[EventType]:
        """Get event type for tool results."""
        mapping = {
            "web_search": EventType.WEB_SEARCH_RESULTS,
            "task_block_search": EventType.TASK_BLOCK_SEARCH_RESULTS,
        }
        return mapping.get(tool_name)

    def _try_parse_workflow(self, text: str) -> Optional[Workflow]:
        """Try to parse workflow JSON from response text."""
        # Look for JSON in code blocks
        json_pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
        matches = re.findall(json_pattern, text)

        for match in matches:
            try:
                data = json.loads(match)
                if "workflow_json" in data and "edges" in data:
                    return Workflow.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                continue

        # Try to find inline JSON
        try:
            # Look for workflow structure
            start = text.find('{"workflow_json"')
            if start == -1:
                start = text.find("{'workflow_json'")
            if start == -1:
                return None

            # Find matching closing brace
            brace_count = 0
            end = start
            for i, char in enumerate(text[start:], start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            if end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                return Workflow.model_validate(data)

        except (json.JSONDecodeError, ValidationError):
            pass

        return None
