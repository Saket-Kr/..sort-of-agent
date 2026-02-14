"""Planner Agent - main LLM-based planning logic."""

import json
import re
from typing import Any

from pydantic import ValidationError

from ..core.enums import EventType, MessageRole
from ..core.exceptions import ClarificationRequiredError
from ..core.interfaces.event_emitter import IEventEmitter
from ..core.interfaces.llm_provider import ILLMProvider, ToolDefinition
from ..core.schemas.messages import ChatMessage, ToolCall
from ..core.schemas.tools import (
    ClarifyOutput,
    PresentAnswerOutput,
    SubmitWorkflowOutput,
    ThinkApproachOutput,
)
from ..core.schemas.workflow import Workflow
from ..core.utils.token_estimation import should_summarize
from ..observability.logger import get_logger
from ..tools.definitions import TOOL_DEFINITIONS
from ..tools.registry import ToolRegistry
from .prompts.planner import get_planner_system_prompt
from .summarizer import MessageSummarizer

logger = get_logger(__name__)


class PlannerAgent:
    """LLM-based planner agent for workflow generation."""

    DEFAULT_MAX_ITERATIONS = 10

    # Tools that are handled specially by the planner (not delegated to registry)
    _OUTPUT_TOOLS = {"think_approach", "present_answer", "submit_workflow"}

    def __init__(
        self,
        llm_provider: ILLMProvider,
        tool_registry: ToolRegistry,
        event_emitter: IEventEmitter | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        summarizer: MessageSummarizer | None = None,
        token_limit: int = 100_000,
    ):
        self._llm = llm_provider
        self._tools = tool_registry
        self._event_emitter = event_emitter
        self._max_iterations = max_iterations
        self._summarizer = summarizer
        self._token_limit = token_limit

    def _get_tool_definitions(self) -> list[ToolDefinition]:
        """Get tool definitions for LLM."""
        return TOOL_DEFINITIONS

    async def plan(
        self,
        conversation_id: str,
        messages: list[ChatMessage],
        user_info: dict | None = None,
        few_shot_examples: str | None = None,
        message_id: str | None = None,
    ) -> tuple[str, Workflow | None]:
        """Execute planning loop.

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

        system_prompt = get_planner_system_prompt(user_info, few_shot_examples)
        system_message = ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)
        full_messages = [system_message] + messages
        tools = self._get_tool_definitions()

        accumulated_response = ""
        submitted_workflow: Workflow | None = None
        iteration = 0

        while iteration < self._max_iterations:
            iteration += 1
            logger.info(
                "LLM iteration",
                conversation_id=conversation_id,
                iteration=iteration,
            )

            # Summarize if messages exceed token limit
            if self._summarizer and should_summarize(
                full_messages, self._token_limit
            ):
                logger.info(
                    "Summarizing messages before LLM call",
                    conversation_id=conversation_id,
                    message_count=len(full_messages),
                )
                # Keep system message, summarize the rest
                summarized = await self._summarizer.summarize(full_messages)
                full_messages = summarized

            tool_calls: list[ToolCall] = []
            response_content = ""

            async for chunk in self._llm.generate_stream(
                messages=full_messages,
                tools=tools,
                temperature=0.7,
            ):
                if chunk.content:
                    response_content += chunk.content
                    accumulated_response += chunk.content

                    if self._event_emitter:
                        await self._event_emitter.emit_stream_chunk(
                            conversation_id, chunk.content, message_id
                        )

                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)

            # If no tool calls, we're done
            if not tool_calls:
                workflow = submitted_workflow or self._try_parse_workflow(
                    accumulated_response
                )
                return accumulated_response, workflow

            # Add assistant message with tool calls
            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response_content if response_content else None,
                tool_calls=tool_calls,
            )
            full_messages.append(assistant_message)

            # Execute tools and collect results
            for tool_call in tool_calls:
                result = await self._execute_tool(
                    conversation_id, tool_call, message_id
                )

                # Handle clarification — raises to orchestrator
                if isinstance(result, ClarifyOutput):
                    raise ClarificationRequiredError(
                        result.clarification_id, result.questions
                    )

                # Handle submit_workflow — capture the workflow
                if (
                    tool_call.name == "submit_workflow"
                    and isinstance(result, SubmitWorkflowOutput)
                    and result.status == "accepted"
                ):
                    submitted_workflow = self._try_parse_workflow_from_tool_call(
                        tool_call.arguments
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
        workflow = submitted_workflow or self._try_parse_workflow(accumulated_response)
        return accumulated_response, workflow

    async def _execute_tool(
        self,
        conversation_id: str,
        tool_call: ToolCall,
        message_id: str | None = None,
    ) -> Any:
        """Execute a tool call, with special handling for output tools."""

        # --- Output tool: think_approach ---
        if tool_call.name == "think_approach":
            content = tool_call.arguments.get("summary", "")
            if self._event_emitter:
                await self._event_emitter.emit_think_approach(
                    conversation_id, content, message_id
                )
            return ThinkApproachOutput(acknowledged=True)

        # --- Output tool: present_answer ---
        if tool_call.name == "present_answer":
            content = tool_call.arguments.get("content", "")
            if self._event_emitter:
                await self._event_emitter.emit_final_answer(
                    conversation_id, content, message_id
                )
            return PresentAnswerOutput(delivered=True)

        # --- Output tool: submit_workflow ---
        if tool_call.name == "submit_workflow":
            return self._handle_submit_workflow(tool_call.arguments)

        # --- Standard tools (web_search, task_block_search, clarify) ---
        executor = self._tools.get(tool_call.name)
        if not executor:
            return {"error": f"Unknown tool: {tool_call.name}"}

        # Emit tool started event
        if self._event_emitter:
            event_type = self._get_tool_started_event(tool_call.name)
            await self._event_emitter.emit_tool_started(
                conversation_id, tool_call.name, event_type, message_id
            )

        try:
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
                        message_id,
                    )

            return result

        except Exception as e:
            return {"error": str(e)}

    def _handle_submit_workflow(self, arguments: dict) -> SubmitWorkflowOutput:
        """Parse and structurally validate a submitted workflow."""
        try:
            workflow = Workflow.model_validate(
                {
                    "workflow_json": arguments.get("workflow_json", []),
                    "edges": arguments.get("edges", []),
                }
            )
        except ValidationError as e:
            return SubmitWorkflowOutput(
                status="needs_revision",
                errors=[
                    f"Invalid workflow structure: {err['msg']}" for err in e.errors()
                ],
            )

        structural_errors = workflow.validate_structure()
        if structural_errors:
            return SubmitWorkflowOutput(
                status="needs_revision",
                errors=structural_errors,
            )

        return SubmitWorkflowOutput(status="accepted")

    def _get_tool_started_event(self, tool_name: str) -> EventType:
        """Get event type for tool started."""
        mapping = {
            "web_search": EventType.WEB_SEARCH_STARTED,
            "task_block_search": EventType.TASK_BLOCK_SEARCH_STARTED,
        }
        return mapping.get(tool_name, EventType.PROCESSING_STARTED)

    def _get_tool_results_event(self, tool_name: str) -> EventType | None:
        """Get event type for tool results."""
        mapping = {
            "web_search": EventType.WEB_SEARCH_RESULTS,
            "task_block_search": EventType.TASK_BLOCK_SEARCH_RESULTS,
        }
        return mapping.get(tool_name)

    def _try_parse_workflow_from_tool_call(
        self, arguments: dict
    ) -> Workflow | None:
        """Parse workflow from submit_workflow tool call arguments."""
        try:
            return Workflow.model_validate(
                {
                    "workflow_json": arguments.get("workflow_json", []),
                    "edges": arguments.get("edges", []),
                }
            )
        except (ValidationError, Exception):
            return None

    def _try_parse_workflow(self, text: str) -> Workflow | None:
        """Try to parse workflow JSON from response text (fallback)."""
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
            start = text.find('{"workflow_json"')
            if start == -1:
                start = text.find("{'workflow_json'")
            if start == -1:
                return None

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
