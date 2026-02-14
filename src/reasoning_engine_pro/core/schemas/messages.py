"""Message and conversation schemas."""

from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..enums import ConversationStatus, MessageRole


class Attachment(BaseModel):
    """File attachment in a message."""

    filename: str
    content_type: str
    content: str  # Base64 encoded content
    size: int


class ToolCall(BaseModel):
    """Tool call from LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result from tool execution."""

    tool_call_id: str
    name: str
    content: str


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: MessageRole
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None  # For tool result messages
    name: Optional[str] = None  # Tool name for tool result messages
    attachments: list[Attachment] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utcnow)

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI API message format."""
        msg: dict[str, Any] = {"role": self.role.value}

        if self.content is not None:
            msg["content"] = self.content

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": str(tc.arguments)},
                }
                for tc in self.tool_calls
            ]

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        if self.name:
            msg["name"] = self.name

        return msg


class UserInfo(BaseModel):
    """User information and context."""

    user_id: Optional[str] = None
    username: Optional[str] = None
    environment: Optional[str] = None
    tenant_id: Optional[str] = None
    permissions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClarificationState(BaseModel):
    """State of a pending clarification."""

    clarification_id: str
    questions: list[str]
    created_at: datetime = Field(default_factory=_utcnow)
    response: Optional[str] = None
    responded_at: Optional[datetime] = None


class ConversationState(BaseModel):
    """Complete state of a conversation."""

    conversation_id: str
    status: ConversationStatus = ConversationStatus.ACTIVE
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    user_info: Optional[UserInfo] = None
    pending_clarification: Optional[ClarificationState] = None
    draft_response: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
