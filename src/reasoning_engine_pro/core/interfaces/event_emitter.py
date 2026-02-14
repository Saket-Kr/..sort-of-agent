"""Event Emitter interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..enums import EventType


class IEventEmitter(ABC):
    """Abstract interface for event emission."""

    @abstractmethod
    async def emit(self, event_type: EventType, payload: dict[str, Any]) -> None:
        """Emit an event with the given type and payload."""
        ...

    @abstractmethod
    async def emit_stream_chunk(
        self,
        conversation_id: str,
        chunk: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit a streaming response chunk."""
        ...

    @abstractmethod
    async def emit_error(
        self,
        conversation_id: str | None,
        error_code: str,
        message: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit an error event."""
        ...

    @abstractmethod
    async def emit_clarification_request(
        self,
        conversation_id: str,
        clarification_id: str,
        questions: list[str],
        message_id: Optional[str] = None,
    ) -> None:
        """Emit a clarification request event."""
        ...

    @abstractmethod
    async def emit_tool_started(
        self,
        conversation_id: str,
        tool_name: str,
        event_type: EventType,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit a tool execution started event."""
        ...

    @abstractmethod
    async def emit_tool_results(
        self,
        conversation_id: str,
        event_type: EventType,
        results: list[dict[str, Any]],
        query_count: int,
        total_results: int,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit tool results event."""
        ...

    @abstractmethod
    async def emit_workflow(
        self,
        conversation_id: str,
        workflow: dict[str, Any],
        job_name: str | None = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit workflow output event."""
        ...

    @abstractmethod
    async def emit_validation_progress(
        self,
        conversation_id: str,
        stage: str,
        progress: float,
        message: str,
        errors: list[str] | None = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit validation progress update."""
        ...

    @abstractmethod
    async def emit_think_approach(
        self,
        conversation_id: str,
        content: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit think_approach event."""
        ...

    @abstractmethod
    async def emit_final_answer(
        self,
        conversation_id: str,
        content: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit final_answer event."""
        ...

    @abstractmethod
    async def emit_chat_ended(
        self,
        conversation_id: str,
    ) -> None:
        """Emit chat_ended event."""
        ...
