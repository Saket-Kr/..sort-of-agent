"""Clarify tool executor."""

import uuid

from ...core.schemas.tools import ClarifyInput, ClarifyOutput
from .base import BaseToolExecutor


class ClarifyExecutor(BaseToolExecutor[ClarifyInput, ClarifyOutput]):
    """Executor for clarification tool."""

    def __init__(self):
        super().__init__(
            name="clarify",
            description=(
                "Request clarification from the user when requirements are ambiguous "
                "or when multiple valid interpretations exist."
            ),
        )

    @property
    def input_schema(self) -> type[ClarifyInput]:
        return ClarifyInput

    @property
    def output_schema(self) -> type[ClarifyOutput]:
        return ClarifyOutput

    @property
    def requires_user_response(self) -> bool:
        """Clarification requires user response before continuing."""
        return True

    async def execute(self, input_data: ClarifyInput) -> ClarifyOutput:
        """
        Execute clarification request.

        Note: This doesn't actually wait for user response. The orchestrator
        handles pausing execution and resuming when user responds.
        """
        clarification_id = str(uuid.uuid4())

        return ClarifyOutput(
            clarification_id=clarification_id,
            questions=input_data.questions,
            status="awaiting_response",
        )
