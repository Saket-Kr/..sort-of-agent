"""Base tool executor implementation."""

from abc import abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ...core.interfaces.tool_executor import IToolExecutor

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class BaseToolExecutor(IToolExecutor[TInput, TOutput], Generic[TInput, TOutput]):
    """Base implementation for tool executors."""

    def __init__(self, name: str, description: str):
        self._name = name
        self._description = description

    @property
    def tool_name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

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

    @abstractmethod
    async def execute(self, input_data: TInput) -> TOutput:
        """Execute the tool."""
        ...

    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function format."""
        schema = self.input_schema.model_json_schema()

        # Remove title and description from root schema
        schema.pop("title", None)

        return {
            "type": "function",
            "function": {
                "name": self._name,
                "description": self._description,
                "parameters": schema,
            },
        }

    def validate_input(self, raw_input: dict[str, Any]) -> TInput:
        """Validate and parse raw input."""
        return self.input_schema.model_validate(raw_input)
