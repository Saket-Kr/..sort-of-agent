"""Inline query refinement — augments the planner prompt instead of making a separate LLM call."""

from ...core.interfaces.query_preprocessor import IQueryPreprocessor
from ...core.schemas.messages import ChatMessage, UserInfo
from ..prompts.domain_data import (
    format_config_sequences,
    format_pillar_module_data,
)


class InlineRefinementPreprocessor(IQueryPreprocessor):
    """Appends refinement guidance directly to the user message.

    No separate LLM call — zero latency overhead. The guidance
    nudges the planner to consider ERP sequencing, multi-environment
    operations, and research-driven block discovery.
    """

    _GUIDANCE = (
        "\n\n---\n"
        "[System Guidance — Query Refinement]\n"
        "Before building the workflow, consider:\n"
        "1. Use web_search and task_block_search to discover available blocks.\n"
        "2. For multi-environment operations, create separate blocks per environment.\n"
        "3. Follow ERP configuration sequencing:\n"
        "{config_sequences}\n"
        "4. Pillar/Module mapping for import/export blocks:\n"
        "{pillar_module_data}\n"
        "5. Prefer pre-built task blocks over AI/Manual blocks when available.\n"
        "6. Use think_approach to outline your plan before building.\n"
    )

    async def preprocess(
        self,
        message: str,
        history: list[ChatMessage],
        user_info: UserInfo | None = None,
    ) -> str:
        guidance = self._GUIDANCE.format(
            config_sequences=format_config_sequences(),
            pillar_module_data=format_pillar_module_data(),
        )
        return message + guidance
