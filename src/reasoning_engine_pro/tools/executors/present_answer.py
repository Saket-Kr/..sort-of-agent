"""Present answer tool executor."""

from ...core.schemas.tools import PresentAnswerInput, PresentAnswerOutput
from .base import BaseToolExecutor


class PresentAnswerExecutor(BaseToolExecutor[PresentAnswerInput, PresentAnswerOutput]):
    """Executor for present_answer tool.

    Returns a delivery confirmation. The planner handles event emission separately.
    """

    def __init__(self):
        super().__init__(
            name="present_answer",
            description="Present final answer content to the user.",
        )

    @property
    def input_schema(self) -> type[PresentAnswerInput]:
        return PresentAnswerInput

    @property
    def output_schema(self) -> type[PresentAnswerOutput]:
        return PresentAnswerOutput

    async def execute(self, input_data: PresentAnswerInput) -> PresentAnswerOutput:
        return PresentAnswerOutput(delivered=True)
