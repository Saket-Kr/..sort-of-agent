"""Think approach tool executor."""

from ...core.schemas.tools import ThinkApproachInput, ThinkApproachOutput
from .base import BaseToolExecutor


class ThinkApproachExecutor(BaseToolExecutor[ThinkApproachInput, ThinkApproachOutput]):
    """Executor for think_approach tool.

    Returns an acknowledgment. The planner handles event emission separately.
    """

    def __init__(self):
        super().__init__(
            name="think_approach",
            description="Communicate current thinking approach to the user.",
        )

    @property
    def input_schema(self) -> type[ThinkApproachInput]:
        return ThinkApproachInput

    @property
    def output_schema(self) -> type[ThinkApproachOutput]:
        return ThinkApproachOutput

    async def execute(self, input_data: ThinkApproachInput) -> ThinkApproachOutput:
        return ThinkApproachOutput(acknowledged=True)
