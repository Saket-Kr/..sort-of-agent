"""Submit workflow tool executor."""

from pydantic import ValidationError as PydanticValidationError

from ...core.schemas.tools import SubmitWorkflowInput, SubmitWorkflowOutput
from ...core.schemas.workflow import Workflow
from .base import BaseToolExecutor


class SubmitWorkflowExecutor(
    BaseToolExecutor[SubmitWorkflowInput, SubmitWorkflowOutput]
):
    """Executor for submit_workflow tool.

    Parses the submitted workflow JSON into a Workflow model and performs
    basic structural validation. The orchestrator handles full validation
    pipeline execution.
    """

    def __init__(self):
        super().__init__(
            name="submit_workflow",
            description="Submit completed workflow for validation.",
        )

    @property
    def input_schema(self) -> type[SubmitWorkflowInput]:
        return SubmitWorkflowInput

    @property
    def output_schema(self) -> type[SubmitWorkflowOutput]:
        return SubmitWorkflowOutput

    async def execute(self, input_data: SubmitWorkflowInput) -> SubmitWorkflowOutput:
        """Parse and structurally validate the submitted workflow."""
        try:
            workflow = Workflow.model_validate(
                {
                    "workflow_json": input_data.workflow_json,
                    "edges": input_data.edges,
                }
            )
        except PydanticValidationError as e:
            return SubmitWorkflowOutput(
                status="needs_revision",
                errors=[f"Invalid workflow structure: {err['msg']}" for err in e.errors()],
            )

        structural_errors = workflow.validate_structure()
        if structural_errors:
            return SubmitWorkflowOutput(
                status="needs_revision",
                errors=structural_errors,
            )

        return SubmitWorkflowOutput(status="accepted")
