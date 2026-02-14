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

THINK_APPROACH_DEFINITION = ToolDefinition(
    name="think_approach",
    description=(
        "Communicate your current thinking approach to the user. Use this to show "
        "your analysis process, what you're about to research, or how you plan to "
        "construct the workflow. Keep summaries concise (1-2 lines)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Your current thinking approach (max 50 words)",
            }
        },
        "required": ["summary"],
    },
)

PRESENT_ANSWER_DEFINITION = ToolDefinition(
    name="present_answer",
    description=(
        "Present your final comprehensive response to the user. Include workflow "
        "summary, explanation of each block, and any identified limitations. "
        "Use markdown formatting for readability."
    ),
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Answer content in markdown format",
            }
        },
        "required": ["content"],
    },
)

SUBMIT_WORKFLOW_DEFINITION = ToolDefinition(
    name="submit_workflow",
    description=(
        "Submit the completed workflow for validation. The workflow will be validated "
        "and you will receive feedback. If validation fails, fix the issues and resubmit."
    ),
    parameters={
        "type": "object",
        "properties": {
            "workflow_json": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of workflow blocks",
            },
            "edges": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of edges connecting blocks",
            },
        },
        "required": ["workflow_json", "edges"],
    },
)

# All tool definitions
TOOL_DEFINITIONS = [
    WEB_SEARCH_DEFINITION,
    TASK_BLOCK_SEARCH_DEFINITION,
    CLARIFY_DEFINITION,
    THINK_APPROACH_DEFINITION,
    PRESENT_ANSWER_DEFINITION,
    SUBMIT_WORKFLOW_DEFINITION,
]


def get_tool_definition(name: str) -> ToolDefinition | None:
    """Get a tool definition by name."""
    for tool in TOOL_DEFINITIONS:
        if tool.name == name:
            return tool
    return None
