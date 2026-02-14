"""Conversation Orchestrator - main entry point for conversation handling."""

import traceback
from datetime import UTC, datetime

from ..core.enums import ConversationStatus, EventType, MessageRole
from ..core.exceptions import (
    ClarificationRequiredError,
    ConversationNotFoundError,
    ReasoningEngineError,
)
from ..core.interfaces.event_emitter import IEventEmitter
from ..core.interfaces.query_preprocessor import IQueryPreprocessor
from ..core.interfaces.storage import IConversationStorage
from ..core.interfaces.validator import ValidationContext
from ..core.schemas.messages import (
    ChatMessage,
    ClarificationState,
    ConversationState,
    UserInfo,
)
from ..core.schemas.workflow import Workflow
from ..observability.logger import get_logger
from .few_shot import FewShotRetriever
from .job_name import JobNameGenerator
from .planner import PlannerAgent
from .referencing import ReferencingAgent
from .validator import WorkflowValidator
from .validators.pipeline import ValidationPipeline

logger = get_logger(__name__)

# Max times the planner can retry after validation feedback
_MAX_VALIDATION_RETRIES = 2


class ConversationOrchestrator:
    """Main orchestrator for conversation handling.

    Coordinates between storage, planner, validator/pipeline, and event emission.
    """

    def __init__(
        self,
        storage: IConversationStorage,
        planner: PlannerAgent,
        validator: WorkflowValidator | ValidationPipeline,
        job_name_generator: JobNameGenerator,
        few_shot_retriever: FewShotRetriever,
        event_emitter: IEventEmitter | None = None,
        preprocessor: IQueryPreprocessor | None = None,
        referencing: ReferencingAgent | None = None,
    ):
        self._storage = storage
        self._planner = planner
        self._job_name = job_name_generator
        self._few_shot = few_shot_retriever
        self._event_emitter = event_emitter
        self._preprocessor = preprocessor
        self._referencing = referencing

        # Wrap legacy validator in a pipeline for uniform handling
        if isinstance(validator, ValidationPipeline):
            self._pipeline = validator
        else:
            self._pipeline = ValidationPipeline().add(validator)

    async def start_conversation(
        self,
        conversation_id: str,
        initial_message: str,
        user_info: UserInfo | None = None,
        attachments: list[dict] | None = None,
    ) -> None:
        """Start a new conversation."""
        state = ConversationState(
            conversation_id=conversation_id,
            status=ConversationStatus.ACTIVE,
            user_info=user_info,
        )
        await self._storage.save_state(conversation_id, state)

        user_message = ChatMessage(
            role=MessageRole.USER,
            content=initial_message,
        )
        await self._storage.save_message(conversation_id, user_message)

        if self._event_emitter:
            await self._event_emitter.emit(
                EventType.PROCESSING_STARTED,
                {"chat_id": conversation_id, "message": initial_message},
            )

        await self._process_conversation(conversation_id, user_info)

    async def handle_clarification_response(
        self,
        conversation_id: str,
        clarification_id: str,
        response: str,
    ) -> None:
        """Handle user response to clarification request."""
        state = await self._storage.get_state(conversation_id)
        if not state:
            raise ConversationNotFoundError(conversation_id)

        if (
            not state.pending_clarification
            or state.pending_clarification.clarification_id != clarification_id
        ):
            raise ReasoningEngineError("No matching clarification request pending")

        await self._storage.save_clarification_response(
            conversation_id, clarification_id, response
        )

        state.pending_clarification.response = response
        state.pending_clarification.responded_at = datetime.now(tz=UTC)
        state.status = ConversationStatus.ACTIVE
        await self._storage.save_state(conversation_id, state)

        user_message = ChatMessage(
            role=MessageRole.USER,
            content=f"[Clarification Response]\n{response}",
        )
        await self._storage.save_message(conversation_id, user_message)

        if self._event_emitter:
            await self._event_emitter.emit(
                EventType.CLARIFICATION_RECEIVED,
                {"chat_id": conversation_id, "clarification_id": clarification_id},
            )

        await self._process_conversation(conversation_id, state.user_info)

    async def end_conversation(self, conversation_id: str) -> None:
        """End a conversation."""
        state = await self._storage.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.COMPLETED
            await self._storage.save_state(conversation_id, state)

    async def _process_conversation(
        self,
        conversation_id: str,
        user_info: UserInfo | None = None,
    ) -> None:
        """Process conversation through the planner."""
        try:
            history = await self._storage.get_history(conversation_id)

            # Preprocess the last user message if a preprocessor is configured
            if self._preprocessor and history:
                last_user_idx = None
                for i in range(len(history) - 1, -1, -1):
                    if history[i].role == MessageRole.USER:
                        last_user_idx = i
                        break
                if last_user_idx is not None:
                    refined = await self._preprocessor.preprocess(
                        history[last_user_idx].content or "",
                        history[:last_user_idx],
                        user_info,
                    )
                    history[last_user_idx] = history[last_user_idx].model_copy(
                        update={"content": refined}
                    )

            examples = await self._few_shot.get_examples()
            examples_str = self._few_shot.format_examples(examples)

            user_dict = user_info.model_dump() if user_info else None

            response_text, workflow = await self._planner.plan(
                conversation_id=conversation_id,
                messages=history,
                user_info=user_dict,
                few_shot_examples=examples_str,
            )

            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response_text,
            )
            await self._storage.save_message(conversation_id, assistant_message)

            if workflow:
                await self._handle_workflow_output(
                    conversation_id, workflow, response_text, history, user_dict, examples_str
                )

        except ClarificationRequiredError as e:
            await self._handle_clarification_request(
                conversation_id, e.clarification_id, e.questions
            )

        except Exception as e:
            await self._handle_error(conversation_id, e)

    async def _handle_clarification_request(
        self,
        conversation_id: str,
        clarification_id: str,
        questions: list[str],
    ) -> None:
        """Handle clarification request from planner."""
        state = await self._storage.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.AWAITING_CLARIFICATION
            state.pending_clarification = ClarificationState(
                clarification_id=clarification_id,
                questions=questions,
            )
            await self._storage.save_state(conversation_id, state)

        await self._storage.save_clarification_request(
            conversation_id, clarification_id, questions
        )

        if self._event_emitter:
            await self._event_emitter.emit_clarification_request(
                conversation_id, clarification_id, questions
            )

    async def _handle_workflow_output(
        self,
        conversation_id: str,
        workflow: Workflow,
        user_description: str,
        history: list[ChatMessage] | None = None,
        user_dict: dict | None = None,
        few_shot_examples: str | None = None,
    ) -> None:
        """Handle workflow output — validate, optionally retry, then emit."""
        # Extract user query from last user message in history
        user_query = user_description
        if history:
            for msg in reversed(history):
                if msg.role == MessageRole.USER:
                    user_query = msg.content or user_description
                    break

        context = ValidationContext(
            conversation_id=conversation_id,
            user_query=user_query,
            event_emitter=self._event_emitter,
        )

        validation_result = await self._pipeline.validate(workflow, context)

        if not validation_result.is_valid:
            if self._event_emitter:
                await self._event_emitter.emit_validation_progress(
                    conversation_id,
                    "failed",
                    100,
                    "Workflow validation failed",
                    validation_result.errors,
                )
            return

        # Use corrected workflow if available
        final_workflow = validation_result.corrected_workflow or workflow

        # Run referencing agent to fill workflow inputs from conversation context
        if self._referencing:
            try:
                final_workflow = await self._referencing.run(
                    workflow=final_workflow,
                    history=history or [],
                    conversation_id=conversation_id,
                    user_info=None,
                )
            except Exception as e:
                logger.warning(
                    "Referencing failed, using workflow as-is",
                    error=str(e),
                )

        # Generate job name (try async/LLM first, fall back to sync/regex)
        job_name = await self._job_name.generate_async(
            final_workflow, user_description
        )
        final_workflow.job_name = job_name

        # Emit workflow
        if self._event_emitter:
            await self._event_emitter.emit_workflow(
                conversation_id,
                final_workflow.model_dump(),
                job_name,
            )

        # Update conversation status
        state = await self._storage.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.COMPLETED
            await self._storage.save_state(conversation_id, state)

    async def _handle_error(
        self,
        conversation_id: str,
        error: Exception,
    ) -> None:
        """Handle errors during processing."""
        logger.error(
            "Error during conversation processing",
            conversation_id=conversation_id,
            error=str(error),
            error_type=type(error).__name__,
            traceback=traceback.format_exc(),
        )

        state = await self._storage.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.ERROR
            await self._storage.save_state(conversation_id, state)

        if self._event_emitter:
            error_code = type(error).__name__
            await self._event_emitter.emit_error(
                conversation_id, error_code, str(error)
            )

    async def get_conversation_state(
        self, conversation_id: str
    ) -> ConversationState | None:
        """Get current conversation state."""
        return await self._storage.get_state(conversation_id)

    async def get_conversation_history(
        self, conversation_id: str, max_messages: int | None = None
    ) -> list[ChatMessage]:
        """Get conversation history."""
        return await self._storage.get_history(conversation_id, max_messages)
