"""Planner system prompt builder."""

from typing import Optional

from .domain_data import (
    format_block_type_descriptions,
    format_config_sequences,
    format_pillar_module_data,
)
from .loader import PromptLoader

_loader = PromptLoader()


def get_planner_system_prompt(
    user_info: Optional[dict] = None,
    few_shot_examples: Optional[str] = None,
) -> str:
    """Build the planner system prompt from template + domain data.

    Falls back to a minimal inline prompt if the template file is missing.
    """
    user_context = ""
    if user_info:
        user_context = (
            "\n## User Context\n"
            f"- User ID: {user_info.get('user_id', 'Unknown')}\n"
            f"- Username: {user_info.get('username', 'Unknown')}\n"
            f"- Email: {user_info.get('email', 'Unknown')}\n"
            f"- Domain: {user_info.get('domain', 'Unknown')}\n"
        )

    examples_section = ""
    if few_shot_examples:
        examples_section = f"\n## Example Workflows\n{few_shot_examples}\n"

    try:
        return _loader.load_with_vars(
            "planner_system",
            block_type_descriptions=format_block_type_descriptions(),
            config_sequences=format_config_sequences(),
            pillar_module_data=format_pillar_module_data(),
            user_context=user_context,
            few_shot_examples=examples_section,
        )
    except FileNotFoundError:
        # Fallback: minimal inline prompt (should not happen in production)
        return _build_fallback_prompt(user_context, examples_section)


def _build_fallback_prompt(user_context: str, examples_section: str) -> str:
    return f"""You are an expert workflow planner for enterprise automation systems.

## Your Role
1. Understand the user's automation requirements
2. Search for relevant information using web_search
3. Find appropriate task blocks using task_block_search
4. Ask clarifying questions using clarify when requirements are ambiguous
5. Use think_approach to communicate your thinking
6. Use present_answer to present your response
7. Use submit_workflow to submit the completed workflow

## Workflow Structure
Workflows consist of blocks (automation steps) and edges (connections).

## Guidelines
1. Always start with a "Start" block (ActionCode: "Start")
2. Use sequential BlockIds (B001, B002, ...) and EdgeIds (E001, E002, ...)
3. Reference outputs using: op-{{BlockId}}-{{OutputName}}
4. Validate all referenced outputs exist before submitting
{user_context}
{examples_section}
"""
