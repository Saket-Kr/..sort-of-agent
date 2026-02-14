"""Error mapper for converting internal exceptions to client-safe messages.

Never leaks internal implementation details, stack traces, or raw error text
to the client. Maps each known exception type to a fixed (error_code, message)
pair that is informative but safe.
"""

from .exceptions import (
    ClarificationRequiredError,
    ConversationNotFoundError,
    LLMProviderError,
    MaxConnectionsExceededError,
    StorageError,
    ToolExecutionError,
    ValidationError,
    WorkflowParseError,
)

# (error_code, user-facing message)
_MAPPING: list[tuple[type[Exception], str, str]] = [
    (
        LLMProviderError,
        "LLM_UNAVAILABLE",
        "The AI service is temporarily unavailable. Please try again.",
    ),
    (
        ToolExecutionError,
        "TOOL_ERROR",
        "A search service is temporarily unavailable.",
    ),
    (
        StorageError,
        "STORAGE_ERROR",
        "A temporary storage issue occurred. Please try again.",
    ),
    (
        ValidationError,
        "VALIDATION_ERROR",
        "We encountered an issue processing your workflow.",
    ),
    (
        WorkflowParseError,
        "PARSE_ERROR",
        "We had trouble generating the workflow. Please try rephrasing your request.",
    ),
    (
        ConversationNotFoundError,
        "NOT_FOUND",
        "Conversation not found.",
    ),
    (
        ClarificationRequiredError,
        "CLARIFICATION_REQUIRED",
        "Additional information is needed to proceed.",
    ),
    (
        MaxConnectionsExceededError,
        "MAX_CONNECTIONS",
        "Server is at capacity. Please try again later.",
    ),
]


class ErrorMapper:
    """Maps internal exceptions to client-safe error responses."""

    @staticmethod
    def to_client_error(exc: Exception) -> tuple[str, str]:
        """Convert an exception to a (error_code, safe_message) tuple.

        Returns a generic message for unmapped exception types.
        """
        for exc_type, code, message in _MAPPING:
            if isinstance(exc, exc_type):
                return code, message
        return "INTERNAL_ERROR", "An unexpected error occurred. Please try again."
