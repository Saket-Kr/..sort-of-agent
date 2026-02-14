"""Referencing prompt builder."""

import json

from .loader import PromptLoader

_loader = PromptLoader()


def get_referencing_prompt(
    workflow_json: str,
    user_query_history: str,
) -> str:
    """Build the referencing system prompt."""
    return _loader.load_with_vars(
        "referencing_system",
        workflow_json=workflow_json,
        user_query_history=user_query_history,
    )
