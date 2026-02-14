"""Workflow validation interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..schemas.workflow import Workflow
from .event_emitter import IEventEmitter


@dataclass
class ValidationContext:
    """Context passed to each validation stage."""

    conversation_id: str
    user_query: str
    message_id: str | None = None
    event_emitter: IEventEmitter | None = None


@dataclass
class ValidationResult:
    """Result from one or more validation stages."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    corrected_workflow: Workflow | None = None

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if other.corrected_workflow is not None:
            self.corrected_workflow = other.corrected_workflow


class IWorkflowValidator(ABC):
    """Interface for a single validation stage."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this validation stage."""
        ...

    @property
    @abstractmethod
    def is_blocking(self) -> bool:
        """If True, pipeline stops on errors from this stage."""
        ...

    @abstractmethod
    async def validate(
        self, workflow: Workflow, context: ValidationContext
    ) -> ValidationResult:
        """Validate a workflow and return results."""
        ...
