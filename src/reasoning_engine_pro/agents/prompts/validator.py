"""Validation prompt builder."""

import json

from ..prompts.domain_data import format_pillar_module_data
from ..prompts.loader import PromptLoader

_loader = PromptLoader()


def get_validation_prompt(
    block: dict,
    task_block_results: list[dict],
    workflow_blocks: list[dict],
    user_query: str,
    edges: list[dict],
) -> str:
    """Build a validation prompt for a single block.

    Args:
        block: The block to validate (dict representation).
        task_block_results: Task block search results for this block.
        workflow_blocks: All blocks in the workflow (for context).
        user_query: Original user request.
        edges: Edge connection data.

    Returns:
        Complete prompt string ready for the LLM.
    """
    return _loader.load_with_vars(
        "validation_system",
        block_json=json.dumps(block, indent=2),
        task_block_results=json.dumps(task_block_results, indent=2),
        full_workflow=json.dumps(workflow_blocks, indent=2),
        user_query=user_query,
        edges_data=json.dumps(edges, indent=2),
        pillar_module_data=format_pillar_module_data(),
    )
