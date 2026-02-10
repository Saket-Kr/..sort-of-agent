"""WebSocket event payload schemas."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from ..enums import EventType
from .workflow import Workflow


class WebSocketEvent(BaseModel):
    """Base WebSocket event structure."""

    event: EventType
    payload: dict[str, Any] = Field(default_factory=dict)


class ProcessingStartedPayload(BaseModel):
    """Payload for processing_started event."""

    chat_id: str
    message: str


class StreamResponsePayload(BaseModel):
    """Payload for stream_response event."""

    chat_id: str
    chunk: str
    is_complete: bool = False


class ClarificationRequestedPayload(BaseModel):
    """Payload for clarification_requested event."""

    chat_id: str
    clarification_id: str
    questions: list[str]


class ClarificationReceivedPayload(BaseModel):
    """Payload for clarification_received event."""

    chat_id: str
    clarification_id: str


class SearchResultsPayload(BaseModel):
    """Payload for search results events."""

    chat_id: str
    results: list[dict[str, Any]]
    query_count: int
    total_results: int


class WorkflowOutputPayload(BaseModel):
    """Payload for opkey_workflow_json event."""

    chat_id: str
    workflow: Workflow
    job_name: Optional[str] = None


class ValidatorProgressPayload(BaseModel):
    """Payload for validator_progress_update event."""

    chat_id: str
    stage: str
    progress: float
    message: str
    errors: list[str] = Field(default_factory=list)


class ErrorPayload(BaseModel):
    """Payload for error event."""

    chat_id: Optional[str] = None
    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class InputAnalysisPayload(BaseModel):
    """Payload for input analysis request/response."""

    chat_id: str
    message: str
    analysis: Optional[dict[str, Any]] = None
