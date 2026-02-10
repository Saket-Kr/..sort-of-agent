"""Job name generator for workflows."""

import re
from datetime import datetime
from typing import Optional

from ..core.schemas.workflow import Workflow


class JobNameGenerator:
    """Generates human-readable job names for workflows."""

    # Action code to human-readable mapping
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

    def __init__(self, max_length: int = 64):
        """
        Initialize job name generator.

        Args:
            max_length: Maximum job name length
        """
        self._max_length = max_length

    def generate(
        self,
        workflow: Workflow,
        user_description: Optional[str] = None,
        include_timestamp: bool = True,
    ) -> str:
        """
        Generate a job name for the workflow.

        Args:
            workflow: Workflow to generate name for
            user_description: Optional user-provided description
            include_timestamp: Whether to include timestamp

        Returns:
            Generated job name
        """
        parts = []

        # Use user description if provided
        if user_description:
            clean_desc = self._clean_text(user_description)
            if clean_desc:
                parts.append(clean_desc[:30])

        # Extract key actions from workflow
        if not parts:
            actions = self._extract_key_actions(workflow)
            if actions:
                parts.append("-".join(actions[:3]))

        # Fallback
        if not parts:
            parts.append("workflow")

        # Add timestamp if requested
        if include_timestamp:
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            parts.append(timestamp)

        # Combine and truncate
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
        # Convert to lowercase
        text = text.lower()
        # Replace spaces and underscores with hyphens
        text = re.sub(r"[\s_]+", "-", text)
        # Remove non-alphanumeric characters except hyphens
        text = re.sub(r"[^a-z0-9-]", "", text)
        # Remove multiple consecutive hyphens
        text = re.sub(r"-+", "-", text)
        # Remove leading/trailing hyphens
        text = text.strip("-")
        return text

    def _sanitize(self, name: str) -> str:
        """Sanitize job name to ensure valid format."""
        # Ensure alphanumeric start
        name = re.sub(r"^[^a-z0-9]+", "", name)
        # Remove invalid characters
        name = re.sub(r"[^a-z0-9-]", "", name)
        # Remove multiple hyphens
        name = re.sub(r"-+", "-", name)
        return name or "workflow"
