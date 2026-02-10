"""Custom exceptions for the reasoning engine."""


class ReasoningEngineError(Exception):
    """Base exception for all reasoning engine errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LLMProviderError(ReasoningEngineError):
    """Error during LLM provider interaction."""

    pass


class ToolExecutionError(ReasoningEngineError):
    """Error during tool execution."""

    def __init__(self, message: str, tool_name: str, details: dict | None = None):
        super().__init__(message, details)
        self.tool_name = tool_name


class StorageError(ReasoningEngineError):
    """Error during storage operations."""

    pass


class ValidationError(ReasoningEngineError):
    """Error during workflow validation."""

    def __init__(self, message: str, validation_errors: list[str] | None = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


class WorkflowParseError(ReasoningEngineError):
    """Error parsing workflow JSON from LLM response."""

    pass


class ConversationNotFoundError(ReasoningEngineError):
    """Conversation not found in storage."""

    def __init__(self, conversation_id: str):
        super().__init__(f"Conversation not found: {conversation_id}")
        self.conversation_id = conversation_id


class ClarificationRequiredError(ReasoningEngineError):
    """Agent requires clarification from user."""

    def __init__(self, clarification_id: str, questions: list[str]):
        super().__init__("Clarification required from user")
        self.clarification_id = clarification_id
        self.questions = questions


class MaxConnectionsExceededError(ReasoningEngineError):
    """Maximum concurrent connections exceeded."""

    def __init__(self, max_connections: int):
        super().__init__(f"Maximum concurrent connections ({max_connections}) exceeded")
        self.max_connections = max_connections
