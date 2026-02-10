"""Tool Registry - singleton pattern for tool management."""

from typing import Any

from ..core.enums import ToolType
from ..core.interfaces.tool_executor import IToolExecutor


class ToolRegistry:
    """Registry for managing tool executors."""

    _instance: "ToolRegistry | None" = None
    _executors: dict[str, IToolExecutor[Any, Any]]

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._executors = {}
        return cls._instance

    def register(self, executor: IToolExecutor[Any, Any]) -> None:
        """
        Register a tool executor.

        Args:
            executor: Tool executor instance
        """
        self._executors[executor.tool_name] = executor

    def get(self, tool_name: str) -> IToolExecutor[Any, Any] | None:
        """
        Get a tool executor by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool executor or None if not found
        """
        return self._executors.get(tool_name)

    def get_by_type(self, tool_type: ToolType) -> IToolExecutor[Any, Any] | None:
        """
        Get a tool executor by ToolType enum.

        Args:
            tool_type: ToolType enum value

        Returns:
            Tool executor or None if not found
        """
        return self._executors.get(tool_type.value)

    def list_tools(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._executors.keys())

    def get_all_definitions(self) -> list[dict[str, Any]]:
        """Get OpenAI function definitions for all registered tools."""
        return [executor.to_openai_function() for executor in self._executors.values()]

    def clear(self) -> None:
        """Clear all registered executors (useful for testing)."""
        self._executors.clear()

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None
