"""Input analysis schemas."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class InputAnalysisRequest(BaseModel):
    """Request body for input analysis."""

    chat_id: str = Field(..., description="Chat/conversation identifier")
    message: str = Field(..., description="User message to analyze")
    context: Optional[dict[str, Any]] = Field(
        None, description="Optional context information"
    )


class EntityReference(BaseModel):
    """A referenced entity in the input."""

    type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0


class InputAnalysisResponse(BaseModel):
    """Response from input analysis."""

    chat_id: str
    message: str
    analysis: dict[str, Any]
    entities: list[EntityReference] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    intent: str = "workflow_creation"
    confidence: float = 1.0
