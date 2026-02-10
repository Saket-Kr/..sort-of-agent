"""Few-shot workflow retriever."""

import json
from typing import Any, Optional

import httpx

from ..config import Settings


class FewShotRetriever:
    """Retrieves few-shot workflow examples for context."""

    # Default examples when API is unavailable
    DEFAULT_EXAMPLES = [
        {
            "description": "Export HCM configuration",
            "workflow": {
                "workflow_json": [
                    {
                        "BlockId": "B001",
                        "Name": "Start",
                        "ActionCode": "Start",
                        "Inputs": [],
                        "Outputs": [],
                    },
                    {
                        "BlockId": "B002",
                        "Name": "Export HCM Config",
                        "ActionCode": "ExportConfigurations",
                        "Inputs": [
                            {"Name": "Module", "StaticValue": "HCM"},
                            {"Name": "Format", "StaticValue": "JSON"},
                        ],
                        "Outputs": [
                            {
                                "Name": "ConfigFile",
                                "OutputVariableName": "op-B002-ConfigFile",
                            }
                        ],
                    },
                ],
                "edges": [{"EdgeID": "E001", "From": "B001", "To": "B002"}],
            },
        },
        {
            "description": "Import data with validation",
            "workflow": {
                "workflow_json": [
                    {
                        "BlockId": "B001",
                        "Name": "Start",
                        "ActionCode": "Start",
                        "Inputs": [],
                        "Outputs": [],
                    },
                    {
                        "BlockId": "B002",
                        "Name": "Validate Input",
                        "ActionCode": "ValidateData",
                        "Inputs": [{"Name": "DataFile", "StaticValue": "input.csv"}],
                        "Outputs": [
                            {
                                "Name": "ValidationResult",
                                "OutputVariableName": "op-B002-ValidationResult",
                            },
                            {"Name": "IsValid", "OutputVariableName": "op-B002-IsValid"},
                        ],
                    },
                    {
                        "BlockId": "B003",
                        "Name": "Import Data",
                        "ActionCode": "ImportData",
                        "Inputs": [
                            {"Name": "DataFile", "StaticValue": "input.csv"},
                            {
                                "Name": "Validation",
                                "ReferencedOutputVariableName": "op-B002-ValidationResult",
                            },
                        ],
                        "Outputs": [
                            {
                                "Name": "ImportResult",
                                "OutputVariableName": "op-B003-ImportResult",
                            }
                        ],
                    },
                ],
                "edges": [
                    {"EdgeID": "E001", "From": "B001", "To": "B002"},
                    {
                        "EdgeID": "E002",
                        "From": "B002",
                        "To": "B003",
                        "EdgeCondition": "true",
                    },
                ],
            },
        },
    ]

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize few-shot retriever.

        Args:
            api_url: Optional API URL for retrieving examples
            api_key: Optional API key
            timeout: Request timeout
        """
        self._api_url = api_url
        self._api_key = api_key
        self._timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings) -> "FewShotRetriever":
        """Create retriever from settings."""
        return cls(
            api_url=getattr(settings, "few_shot_api_url", None),
            api_key=getattr(settings, "few_shot_api_key", None),
        )

    async def get_examples(
        self, query: Optional[str] = None, max_examples: int = 3
    ) -> list[dict[str, Any]]:
        """
        Get few-shot workflow examples.

        Args:
            query: Optional query to find relevant examples
            max_examples: Maximum number of examples to return

        Returns:
            List of workflow examples
        """
        # Try API first if configured
        if self._api_url and self._api_key:
            try:
                return await self._fetch_from_api(query, max_examples)
            except Exception:
                pass  # Fall back to defaults

        # Return default examples
        return self.DEFAULT_EXAMPLES[:max_examples]

    async def _fetch_from_api(
        self, query: Optional[str], max_examples: int
    ) -> list[dict[str, Any]]:
        """Fetch examples from API."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._api_url}/examples/search",
                json={"query": query, "limit": max_examples},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            return response.json().get("examples", [])

    def format_examples(self, examples: list[dict[str, Any]]) -> str:
        """
        Format examples for inclusion in prompt.

        Args:
            examples: List of workflow examples

        Returns:
            Formatted string for prompt
        """
        formatted = []
        for i, example in enumerate(examples, 1):
            desc = example.get("description", f"Example {i}")
            workflow = example.get("workflow", {})
            formatted.append(
                f"### Example {i}: {desc}\n```json\n{json.dumps(workflow, indent=2)}\n```"
            )

        return "\n\n".join(formatted)
