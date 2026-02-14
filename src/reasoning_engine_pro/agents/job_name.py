"""Job name generator for workflows."""

import re
from datetime import UTC, datetime

from ..core.enums import MessageRole
from ..core.interfaces.llm_provider import ILLMProvider
from ..core.schemas.messages import ChatMessage
from ..core.schemas.workflow import Workflow
from ..observability.logger import get_logger
from .prompts.loader import PromptLoader

logger = get_logger(__name__)

_loader = PromptLoader()


class JobNameGenerator:
    """Generates human-readable job names for workflows.

    Tries LLM-based generation first (if llm_provider is set),
    falls back to regex-based extraction.
    """

    ACTION_DESCRIPTIONS = {
        "Start": "start",
        "ExportConfigurations": "export-config",
        "ImportData": "import-data",
        "ValidateData": "validate",
        "AskWilfred": "ask-wilfred",
        "TransformData": "transform",
        "NotifyUser": "notify",
        "ConditionalBranch": "condition",
        "LoopBlock": "loop",
        "EndLoop": "end-loop",
        "ErrorHandler": "error-handler",
    }

    def __init__(
        self,
        max_length: int = 64,
        llm_provider: ILLMProvider | None = None,
    ):
        self._max_length = max_length
        self._llm = llm_provider

    def generate(
        self,
        workflow: Workflow,
        user_description: str | None = None,
        include_timestamp: bool = True,
    ) -> str:
        """Generate a job name. Synchronous — uses regex only."""
        return self._generate_regex(workflow, user_description, include_timestamp)

    async def generate_async(
        self,
        workflow: Workflow,
        user_description: str | None = None,
        include_timestamp: bool = True,
    ) -> str:
        """Generate a job name. Tries LLM first, falls back to regex."""
        if self._llm and user_description:
            try:
                llm_name = await self._generate_llm(user_description)
                if llm_name:
                    return llm_name
            except Exception as e:
                logger.warning("LLM job name generation failed", error=str(e))

        return self._generate_regex(workflow, user_description, include_timestamp)

    async def _generate_llm(self, user_description: str) -> str | None:
        """Generate job name using LLM."""
        system_prompt = _loader.load("job_name_system")

        response = await self._llm.generate(
            messages=[
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_description),
            ],
            temperature=0.3,
        )

        name = (response.content or "").strip().strip('"\'`')
        if not name or name.lower().startswith("error"):
            return None

        # Sanitize LLM output
        name = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip()
        if len(name) > 80:
            name = name[:77] + "..."
        return name or None

    def _generate_regex(
        self,
        workflow: Workflow,
        user_description: str | None = None,
        include_timestamp: bool = True,
    ) -> str:
        """Generate job name using regex extraction."""
        parts = []

        if user_description:
            clean_desc = self._clean_text(user_description)
            if clean_desc:
                parts.append(clean_desc[:30])

        if not parts:
            actions = self._extract_key_actions(workflow)
            if actions:
                parts.append("-".join(actions[:3]))

        if not parts:
            parts.append("workflow")

        if include_timestamp:
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
            parts.append(timestamp)

        job_name = "-".join(parts)
        job_name = self._sanitize(job_name)

        if len(job_name) > self._max_length:
            job_name = job_name[: self._max_length - 3] + "..."

        return job_name

    def _extract_key_actions(self, workflow: Workflow) -> list[str]:
        """Extract key action descriptions from workflow."""
        actions = []
        for block in workflow.workflow_json:
            if block.ActionCode == "Start":
                continue
            desc = self.ACTION_DESCRIPTIONS.get(
                block.ActionCode, self._clean_text(block.ActionCode)
            )
            if desc and desc not in actions:
                actions.append(desc)
        return actions

    def _clean_text(self, text: str) -> str:
        """Clean text for use in job name."""
        text = text.lower()
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"[^a-z0-9-]", "", text)
        text = re.sub(r"-+", "-", text)
        text = text.strip("-")
        return text

    def _sanitize(self, name: str) -> str:
        """Sanitize job name to ensure valid format."""
        name = re.sub(r"^[^a-z0-9]+", "", name)
        name = re.sub(r"[^a-z0-9-]", "", name)
        name = re.sub(r"-+", "-", name)
        return name or "workflow"
