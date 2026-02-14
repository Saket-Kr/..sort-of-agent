"""Core enumerations for the reasoning engine."""

from enum import Enum


class MessageRole(str, Enum):
    """Message roles in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolType(str, Enum):
    """Available tool types."""

    WEB_SEARCH = "web_search"
    TASK_BLOCK_SEARCH = "task_block_search"
    CLARIFY = "clarify"


class EventType(str, Enum):
    """WebSocket event types."""

    # Client -> Server
    START_CHAT = "start_chat"
    PROVIDE_CLARIFICATION = "provide_clarification"
    END_CHAT = "end_chat"
    PING = "ping"
    INPUT_ANALYSIS = "input_analysis"

    # Server -> Client
    PROCESSING_STARTED = "processing_started"
    STREAM_RESPONSE = "stream_response"
    THINK_APPROACH = "think_approach"
    FINAL_ANSWER = "final_answer"
    CLARIFICATION_REQUESTED = "clarification_requested"
    CLARIFICATION_RECEIVED = "clarification_received"
    CLARIFICATION_PROCESSING = "clarification_processing"
    WEB_SEARCH_STARTED = "web_search_started"
    WEB_SEARCH_RESULTS = "web_search_results"
    TASK_BLOCK_SEARCH_STARTED = "task_block_search_started"
    TASK_BLOCK_SEARCH_RESULTS = "task_block_search_results"
    OPKEY_WORKFLOW_JSON = "opkey_workflow_json"
    VALIDATOR_PROGRESS_UPDATE = "validator_progress_update"
    CHAT_ENDED = "chat_ended"
    REFERENCING_STARTED = "referencing_started"
    QUERY_REFINEMENT_STARTED = "query_refinement_started"
    QUERY_REFINEMENT_COMPLETED = "query_refinement_completed"
    CONTINUATION_ERROR = "continuation_error"
    ERROR = "error"
    MAX_CONCURRENT_CONNECTIONS_EXCEEDED = "max_concurrent_connections_exceeded"
    PONG = "pong"


class ConversationStatus(str, Enum):
    """Status of a conversation."""

    ACTIVE = "active"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    COMPLETED = "completed"
    ERROR = "error"


class ValidationStatus(str, Enum):
    """Status of workflow validation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
