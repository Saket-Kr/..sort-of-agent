"""Referencing agent — fills mandatory workflow inputs from conversation context."""

import json
import re

from pydantic import ValidationError

from ..core.enums import EventType, MessageRole
from ..core.interfaces.event_emitter import IEventEmitter
from ..core.interfaces.llm_provider import ILLMProvider
from ..core.schemas.messages import ChatMessage, UserInfo
from ..core.schemas.workflow import Workflow
from ..observability.logger import get_logger
from .prompts.referencing import get_referencing_prompt

logger = get_logger(__name__)


class ReferencingAgent:
    """Fills mandatory workflow inputs by extracting values from conversation context.

    Given a validated workflow and the user's conversation history, this agent
    uses an LLM to populate empty mandatory input fields with appropriate values.
    """

    def __init__(
        self,
        llm_provider: ILLMProvider,
        event_emitter: IEventEmitter | None = None,
    ):
        self._llm = llm_provider
        self._event_emitter = event_emitter

    async def run(
        self,
        workflow: Workflow,
        history: list[ChatMessage],
        conversation_id: str | None = None,
        user_info: UserInfo | None = None,
    ) -> Workflow:
        """Fill workflow inputs from conversation context.

        Returns the workflow with filled inputs, or the original if
        referencing fails.
        """
        if self._event_emitter and conversation_id:
            await self._event_emitter.emit(
                EventType.REFERENCING_STARTED,
                {"chat_id": conversation_id, "message": "Filling workflow inputs..."},
            )

        # Build user query history from messages
        query_parts: list[str] = []
        for msg in history:
            if msg.role in (MessageRole.USER, MessageRole.ASSISTANT):
                role = msg.role.value.capitalize()
                query_parts.append(f"{role}: {msg.content or ''}")

        user_query_history = "\n\n".join(query_parts)
        workflow_json = json.dumps(workflow.model_dump(), indent=2)

        prompt = get_referencing_prompt(
            workflow_json=workflow_json,
            user_query_history=user_query_history,
        )

        try:
            response = await self._llm.generate(
                messages=[
                    ChatMessage(role=MessageRole.USER, content=prompt),
                ],
                temperature=0.1,
            )

            response_text = response.content or ""
            updated = self._parse_workflow_from_response(response_text)

            if updated:
                logger.info("Referencing completed, inputs populated")
                return updated

            logger.warning("Could not parse workflow from referencing response")
            return workflow

        except Exception as e:
            logger.warning("Referencing failed", error=str(e))
            return workflow

    def _parse_workflow_from_response(self, text: str) -> Workflow | None:
        """Extract and parse workflow JSON from the LLM response."""
        # Try JSON in code fences first
        json_matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        for match in json_matches:
            try:
                data = json.loads(match)
                return Workflow.model_validate(data)
            except (json.JSONDecodeError, ValidationError):
                continue

        # Try raw JSON
        try:
            start = text.find("{")
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
                data = json.loads(text[start:end])
                return Workflow.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            pass

        return None
