"""Conversation Orchestrator - main entry point for conversation handling."""

import traceback
import uuid
from datetime import datetime
from typing import Any, Optional

from ..core.enums import ConversationStatus, EventType, MessageRole
from ..observability.logger import get_logger

logger = get_logger(__name__)
from ..core.exceptions import (
    ClarificationRequiredError,
    ConversationNotFoundError,
    ReasoningEngineError,
)
from ..core.interfaces.event_emitter import IEventEmitter
from ..core.interfaces.storage import IConversationStorage
from ..core.schemas.messages import (
    ClarificationState,
    ChatMessage,
    ConversationState,
    UserInfo,
)
from ..core.schemas.workflow import Workflow
from .few_shot import FewShotRetriever
from .job_name import JobNameGenerator
from .planner import PlannerAgent
from .validator import WorkflowValidator


class ConversationOrchestrator:
    """
    Main orchestrator for conversation handling.

    Coordinates between storage, planner, validator, and event emission.
    """

    def __init__(
        self,
        storage: IConversationStorage,
        planner: PlannerAgent,
        validator: WorkflowValidator,
        job_name_generator: JobNameGenerator,
        few_shot_retriever: FewShotRetriever,
        event_emitter: Optional[IEventEmitter] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            storage: Conversation storage
            planner: Planner agent
            validator: Workflow validator
            job_name_generator: Job name generator
            few_shot_retriever: Few-shot example retriever
            event_emitter: Optional event emitter
        """
        self._storage = storage
        self._planner = planner
        self._validator = validator
        self._job_name = job_name_generator
        self._few_shot = few_shot_retriever
        self._event_emitter = event_emitter

    async def start_conversation(
        self,
        conversation_id: str,
        initial_message: str,
        user_info: Optional[UserInfo] = None,
        attachments: Optional[list[dict]] = None,
    ) -> None:
        """
        Start a new conversation.

        Args:
            conversation_id: Unique conversation identifier
            initial_message: User's initial message
            user_info: Optional user information
            attachments: Optional message attachments
        """
        # Create conversation state
        state = ConversationState(
            conversation_id=conversation_id,
            status=ConversationStatus.ACTIVE,
            user_info=user_info,
        )
        await self._storage.save_state(conversation_id, state)

        # Save initial user message
        user_message = ChatMessage(
            role=MessageRole.USER,
            content=initial_message,
        )
        await self._storage.save_message(conversation_id, user_message)

        # Emit processing started
        if self._event_emitter:
            await self._event_emitter.emit(
                EventType.PROCESSING_STARTED,
                {"chat_id": conversation_id, "message": initial_message},
            )

        # Process the message
        await self._process_conversation(conversation_id, user_info)

    async def handle_clarification_response(
        self,
        conversation_id: str,
        clarification_id: str,
        response: str,
    ) -> None:
        """
        Handle user response to clarification request.

        Args:
            conversation_id: Conversation identifier
            clarification_id: Clarification request identifier
            response: User's response
        """
        # Get conversation state
        state = await self._storage.get_state(conversation_id)
        if not state:
            raise ConversationNotFoundError(conversation_id)

        # Verify clarification is pending
        if (
            not state.pending_clarification
            or state.pending_clarification.clarification_id != clarification_id
        ):
            raise ReasoningEngineError("No matching clarification request pending")

        # Save response
        await self._storage.save_clarification_response(
            conversation_id, clarification_id, response
        )

        # Update state
        state.pending_clarification.response = response
        state.pending_clarification.responded_at = datetime.utcnow()
        state.status = ConversationStatus.ACTIVE
        await self._storage.save_state(conversation_id, state)

        # Add clarification response as user message
        user_message = ChatMessage(
            role=MessageRole.USER,
            content=f"[Clarification Response]\n{response}",
        )
        await self._storage.save_message(conversation_id, user_message)

        # Emit clarification received
        if self._event_emitter:
            await self._event_emitter.emit(
                EventType.CLARIFICATION_RECEIVED,
                {"chat_id": conversation_id, "clarification_id": clarification_id},
            )

        # Continue processing
        await self._process_conversation(conversation_id, state.user_info)

    async def end_conversation(self, conversation_id: str) -> None:
        """
        End a conversation.

        Args:
            conversation_id: Conversation identifier
        """
        state = await self._storage.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.COMPLETED
            await self._storage.save_state(conversation_id, state)

    async def _process_conversation(
        self,
        conversation_id: str,
        user_info: Optional[UserInfo] = None,
    ) -> None:
        """Process conversation through the planner."""
        try:
            # Get conversation history
            history = await self._storage.get_history(conversation_id)

            # Get few-shot examples
            examples = await self._few_shot.get_examples()
            examples_str = self._few_shot.format_examples(examples)

            # User info dict
            user_dict = user_info.model_dump() if user_info else None

            # Run planner
            response_text, workflow = await self._planner.plan(
                conversation_id=conversation_id,
                messages=history,
                user_info=user_dict,
                few_shot_examples=examples_str,
            )

            # Save assistant response
            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response_text,
            )
            await self._storage.save_message(conversation_id, assistant_message)

            # If workflow generated, validate and emit
            if workflow:
                await self._handle_workflow_output(
                    conversation_id, workflow, response_text
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
        # Update state
        state = await self._storage.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.AWAITING_CLARIFICATION
            state.pending_clarification = ClarificationState(
                clarification_id=clarification_id,
                questions=questions,
            )
            await self._storage.save_state(conversation_id, state)

        # Save clarification request
        await self._storage.save_clarification_request(
            conversation_id, clarification_id, questions
        )

        # Emit clarification requested
        if self._event_emitter:
            await self._event_emitter.emit_clarification_request(
                conversation_id, clarification_id, questions
            )

    async def _handle_workflow_output(
        self,
        conversation_id: str,
        workflow: Workflow,
        user_description: str,
    ) -> None:
        """Handle workflow output - validate and emit."""
        # Validate workflow
        validation_result = await self._validator.validate(
            workflow, conversation_id
        )

        if not validation_result.is_valid:
            # Emit validation errors
            if self._event_emitter:
                await self._event_emitter.emit_validation_progress(
                    conversation_id,
                    "failed",
                    100,
                    "Workflow validation failed",
                    validation_result.errors,
                )
            return

        # Generate job name
        job_name = self._job_name.generate(workflow, user_description)
        workflow.job_name = job_name

        # Emit workflow
        if self._event_emitter:
            await self._event_emitter.emit_workflow(
                conversation_id,
                workflow.model_dump(),
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
        # Log the full error with traceback
        logger.error(
            "Error during conversation processing",
            conversation_id=conversation_id,
            error=str(error),
            error_type=type(error).__name__,
            traceback=traceback.format_exc(),
        )

        # Update state
        state = await self._storage.get_state(conversation_id)
        if state:
            state.status = ConversationStatus.ERROR
            await self._storage.save_state(conversation_id, state)

        # Emit error
        if self._event_emitter:
            error_code = type(error).__name__
            await self._event_emitter.emit_error(
                conversation_id, error_code, str(error)
            )

    async def get_conversation_state(
        self, conversation_id: str
    ) -> Optional[ConversationState]:
        """Get current conversation state."""
        return await self._storage.get_state(conversation_id)

    async def get_conversation_history(
        self, conversation_id: str, max_messages: Optional[int] = None
    ) -> list[ChatMessage]:
        """Get conversation history."""
        return await self._storage.get_history(conversation_id, max_messages)
