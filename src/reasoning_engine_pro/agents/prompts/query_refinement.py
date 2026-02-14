"""Query refinement prompt builder."""

from .domain_data import format_config_sequences, format_pillar_module_data
from .loader import PromptLoader

_loader = PromptLoader()


def get_query_refinement_prompt() -> str:
    """Build the query refinement system prompt with domain data."""
    return _loader.load_with_vars(
        "query_refinement_system",
        config_sequences=format_config_sequences(),
        pillar_module_data=format_pillar_module_data(),
    )
