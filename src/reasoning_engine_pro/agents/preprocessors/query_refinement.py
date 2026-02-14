"""Separate-call query refinement preprocessor."""

from ...core.enums import EventType, MessageRole
from ...core.interfaces.event_emitter import IEventEmitter
from ...core.interfaces.llm_provider import ILLMProvider
from ...core.interfaces.query_preprocessor import IQueryPreprocessor
from ...core.schemas.messages import ChatMessage, UserInfo
from ...observability.logger import get_logger
from ..prompts.query_refinement import get_query_refinement_prompt

logger = get_logger(__name__)


class QueryRefinementPreprocessor(IQueryPreprocessor):
    """Calls the LLM to refine/augment the user's query before planning.

    Emits query_refinement_started / query_refinement_completed events.
    """

    def __init__(
        self,
        llm_provider: ILLMProvider,
        event_emitter: IEventEmitter | None = None,
    ):
        self._llm = llm_provider
        self._event_emitter = event_emitter

    async def preprocess(
        self,
        message: str,
        history: list[ChatMessage],
        user_info: UserInfo | None = None,
    ) -> str:
        conversation_id = ""
        if self._event_emitter:
            await self._event_emitter.emit(
                EventType.QUERY_REFINEMENT_STARTED,
                {"message": "Refining query..."},
            )

        try:
            system_prompt = get_query_refinement_prompt()
            user_prompt = (
                "Transform this user query by adding comprehensive guidance "
                "for the workflow planner:\n\n"
                f"{message}\n\n"
                "Write as a journey of discovery:\n"
                "- Start with research directions\n"
                "- Show how research findings lead to different paths\n"
                "- Be explicit about multi-environment operations\n"
                "- Guide flexible block selection based on what's found\n"
                "- Include production safeguards when applicable"
            )

            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt),
            ]

            response = await self._llm.generate(
                messages=messages,
                temperature=0.5,
            )

            refined = response.content or message
            logger.info(
                "Query refined",
                original_length=len(message),
                refined_length=len(refined),
            )
        except Exception as e:
            logger.warning("Query refinement failed, using original", error=str(e))
            refined = message

        if self._event_emitter:
            await self._event_emitter.emit(
                EventType.QUERY_REFINEMENT_COMPLETED,
                {"message": "Query refinement complete"},
            )

        return refined
