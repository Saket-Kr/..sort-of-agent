"""Tool Executor interface."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class IToolExecutor(ABC, Generic[TInput, TOutput]):
    """Abstract interface for tool executors."""

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Get the tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool description."""
        ...

    @abstractmethod
    async def execute(self, input_data: TInput) -> TOutput:
        """
        Execute the tool with the given input.

        Args:
            input_data: Validated input for the tool

        Returns:
            Tool execution output
        """
        ...

    @abstractmethod
    def to_openai_function(self) -> dict[str, Any]:
        """
        Convert tool to OpenAI function calling format.

        Returns:
            Dictionary in OpenAI function format
        """
        ...

    @property
    @abstractmethod
    def input_schema(self) -> type[TInput]:
        """Get the Pydantic model for input validation."""
        ...

    @property
    @abstractmethod
    def output_schema(self) -> type[TOutput]:
        """Get the Pydantic model for output."""
        ...

    @property
    def requires_user_response(self) -> bool:
        """Check if tool execution requires user response before continuing."""
        return False

    def validate_input(self, raw_input: dict[str, Any]) -> TInput:
        """Validate and parse raw input into typed input."""
        return self.input_schema.model_validate(raw_input)
