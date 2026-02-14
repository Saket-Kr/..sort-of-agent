"""Validation pipeline — runs multiple validation stages in sequence."""

from ...core.interfaces.validator import (
    IWorkflowValidator,
    ValidationContext,
    ValidationResult,
)
from ...core.schemas.workflow import Workflow
from ...observability.logger import get_logger

logger = get_logger(__name__)


class ValidationPipeline:
    """Runs validation stages sequentially, threading corrected workflows between them."""

    def __init__(self) -> None:
        self._stages: list[IWorkflowValidator] = []

    def add(self, validator: IWorkflowValidator) -> "ValidationPipeline":
        """Add a validation stage. Returns self for chaining."""
        self._stages.append(validator)
        return self

    @property
    def stages(self) -> list[IWorkflowValidator]:
        return list(self._stages)

    async def validate(
        self, workflow: Workflow, context: ValidationContext
    ) -> ValidationResult:
        """Run all stages. Stops early if a blocking stage has errors."""
        combined = ValidationResult()
        current_workflow = workflow

        for stage in self._stages:
            logger.info(
                "Running validation stage",
                stage=stage.name,
                conversation_id=context.conversation_id,
            )

            result = await stage.validate(current_workflow, context)
            combined.merge(result)

            if stage.is_blocking and not result.is_valid:
                logger.info(
                    "Blocking stage failed, stopping pipeline",
                    stage=stage.name,
                    errors=result.errors,
                )
                return combined

            if result.corrected_workflow is not None:
                current_workflow = result.corrected_workflow

        combined.corrected_workflow = current_workflow
        return combined
