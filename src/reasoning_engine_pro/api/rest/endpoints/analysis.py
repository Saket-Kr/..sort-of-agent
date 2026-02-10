"""Input analysis endpoint."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...dependencies import Dependencies, get_dependencies

router = APIRouter()


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


@router.post(
    "/wilfred_v4/planner-dashboard/input_analysis",
    response_model=InputAnalysisResponse,
)
async def analyze_input(
    request: InputAnalysisRequest,
    deps: Dependencies = Depends(get_dependencies),
) -> InputAnalysisResponse:
    """
    Analyze user input for entities, references, and intent.

    This endpoint performs lightweight analysis on user input to:
    - Extract entity references (modules, actions, etc.)
    - Identify workflow-related intent
    - Detect referenced variables or blocks
    """
    try:
        # Perform analysis
        analysis_result = _analyze_message(request.message, request.context)

        return InputAnalysisResponse(
            chat_id=request.chat_id,
            message=request.message,
            analysis=analysis_result["analysis"],
            entities=analysis_result["entities"],
            references=analysis_result["references"],
            intent=analysis_result["intent"],
            confidence=analysis_result["confidence"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _analyze_message(
    message: str, context: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Analyze a message for entities and intent.

    This is a simplified implementation. In production, this could use
    NER models, regex patterns, or other analysis techniques.
    """
    message_lower = message.lower()
    entities: list[EntityReference] = []
    references: list[str] = []

    # Common module patterns
    modules = ["hcm", "erp", "scm", "fin", "crm", "procurement"]
    for module in modules:
        if module in message_lower:
            start = message_lower.find(module)
            entities.append(
                EntityReference(
                    type="module",
                    value=module.upper(),
                    start=start,
                    end=start + len(module),
                )
            )

    # Common action patterns
    actions = [
        ("export", "export"),
        ("import", "import"),
        ("migrate", "migration"),
        ("validate", "validation"),
        ("transform", "transformation"),
        ("configure", "configuration"),
    ]
    for pattern, action_type in actions:
        if pattern in message_lower:
            start = message_lower.find(pattern)
            entities.append(
                EntityReference(
                    type="action",
                    value=action_type,
                    start=start,
                    end=start + len(pattern),
                )
            )

    # Detect references (e.g., "op-B001-File")
    import re
    ref_pattern = r"op-[A-Z]\d{3}-\w+"
    for match in re.finditer(ref_pattern, message):
        references.append(match.group())

    # Determine intent
    intent = "workflow_creation"
    confidence = 0.8

    if "create" in message_lower or "build" in message_lower:
        intent = "workflow_creation"
        confidence = 0.9
    elif "modify" in message_lower or "update" in message_lower:
        intent = "workflow_modification"
        confidence = 0.85
    elif "explain" in message_lower or "what" in message_lower:
        intent = "information_request"
        confidence = 0.75
    elif "help" in message_lower:
        intent = "help_request"
        confidence = 0.9

    return {
        "analysis": {
            "word_count": len(message.split()),
            "has_entities": len(entities) > 0,
            "has_references": len(references) > 0,
        },
        "entities": entities,
        "references": references,
        "intent": intent,
        "confidence": confidence,
    }
