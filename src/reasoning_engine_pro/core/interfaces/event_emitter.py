"""Event Emitter interface."""

from abc import ABC, abstractmethod
from typing import Any

from ..enums import EventType


class IEventEmitter(ABC):
    """Abstract interface for event emission."""

    @abstractmethod
    async def emit(self, event_type: EventType, payload: dict[str, Any]) -> None:
        """
        Emit an event.

        Args:
            event_type: Type of event to emit
            payload: Event payload data
        """
        ...

    @abstractmethod
    async def emit_stream_chunk(self, conversation_id: str, chunk: str) -> None:
        """
        Emit a streaming response chunk.

        Args:
            conversation_id: Conversation identifier
            chunk: Content chunk to emit
        """
        ...

    @abstractmethod
    async def emit_error(
        self, conversation_id: str | None, error_code: str, message: str
    ) -> None:
        """
        Emit an error event.

        Args:
            conversation_id: Optional conversation identifier
            error_code: Error code
            message: Error message
        """
        ...

    @abstractmethod
    async def emit_clarification_request(
        self, conversation_id: str, clarification_id: str, questions: list[str]
    ) -> None:
        """
        Emit a clarification request event.

        Args:
            conversation_id: Conversation identifier
            clarification_id: Unique clarification identifier
            questions: List of questions for the user
        """
        ...

    @abstractmethod
    async def emit_tool_started(
        self, conversation_id: str, tool_name: str, event_type: EventType
    ) -> None:
        """
        Emit a tool execution started event.

        Args:
            conversation_id: Conversation identifier
            tool_name: Name of the tool
            event_type: Specific event type for this tool
        """
        ...

    @abstractmethod
    async def emit_tool_results(
        self,
        conversation_id: str,
        event_type: EventType,
        results: list[dict[str, Any]],
        query_count: int,
        total_results: int,
    ) -> None:
        """
        Emit tool results event.

        Args:
            conversation_id: Conversation identifier
            event_type: Specific event type for this tool's results
            results: List of results
            query_count: Number of queries executed
            total_results: Total number of results
        """
        ...

    @abstractmethod
    async def emit_workflow(
        self,
        conversation_id: str,
        workflow: dict[str, Any],
        job_name: str | None = None,
    ) -> None:
        """
        Emit workflow output event.

        Args:
            conversation_id: Conversation identifier
            workflow: Workflow JSON data
            job_name: Optional generated job name
        """
        ...

    @abstractmethod
    async def emit_validation_progress(
        self,
        conversation_id: str,
        stage: str,
        progress: float,
        message: str,
        errors: list[str] | None = None,
    ) -> None:
        """
        Emit validation progress update.

        Args:
            conversation_id: Conversation identifier
            stage: Current validation stage
            progress: Progress percentage (0-100)
            message: Status message
            errors: Optional list of validation errors
        """
        ...
