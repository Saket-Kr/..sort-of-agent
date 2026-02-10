"""OpenAI function definitions for tools."""

from ..core.interfaces.llm_provider import ToolDefinition

WEB_SEARCH_DEFINITION = ToolDefinition(
    name="web_search",
    description=(
        "Search the web for information about enterprise systems, business processes, "
        "technical details, and domain-specific knowledge. Use this when you need "
        "external information not available in the conversation context."
    ),
    parameters={
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of search queries to execute (1-10 queries)",
                "minItems": 1,
                "maxItems": 10,
            }
        },
        "required": ["queries"],
    },
)

TASK_BLOCK_SEARCH_DEFINITION = ToolDefinition(
    name="task_block_search",
    description=(
        "Search for available task blocks that can be used in workflows. "
        "Task blocks are pre-built automation components with specific actions like "
        "ExportConfigurations, ImportData, AskWilfred, etc. Use this to find "
        "appropriate blocks for building workflows."
    ),
    parameters={
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of queries to search for task blocks (1-10 queries)",
                "minItems": 1,
                "maxItems": 10,
            }
        },
        "required": ["queries"],
    },
)

CLARIFY_DEFINITION = ToolDefinition(
    name="clarify",
    description=(
        "Request clarification from the user when the requirements are ambiguous, "
        "incomplete, or when multiple valid interpretations exist. Use this to gather "
        "necessary information before proceeding with workflow creation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of questions to ask the user (1-5 questions)",
                "minItems": 1,
                "maxItems": 5,
            }
        },
        "required": ["questions"],
    },
)

# All tool definitions
TOOL_DEFINITIONS = [
    WEB_SEARCH_DEFINITION,
    TASK_BLOCK_SEARCH_DEFINITION,
    CLARIFY_DEFINITION,
]


def get_tool_definition(name: str) -> ToolDefinition | None:
    """Get a tool definition by name."""
    for tool in TOOL_DEFINITIONS:
        if tool.name == name:
            return tool
    return None
