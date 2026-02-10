"""Mock LLM responses for testing."""

import json


class MockLLMResponses:
    """Collection of mock LLM responses."""

    @staticmethod
    def simple_text_response() -> str:
        """Simple text response."""
        return "I'll help you create a workflow for that task."

    @staticmethod
    def workflow_response() -> str:
        """Response with workflow JSON."""
        workflow = {
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
                    ],
                    "Outputs": [
                        {
                            "Name": "ConfigFile",
                            "OutputVariableName": "op-B002-ConfigFile",
                        },
                    ],
                },
            ],
            "edges": [
                {"EdgeID": "E001", "From": "B001", "To": "B002"},
            ],
        }

        return f"""Based on your request, here's the workflow:

```json
{json.dumps(workflow, indent=2)}
```

This workflow will export HCM configuration."""

    @staticmethod
    def clarification_response() -> dict:
        """Mock tool call for clarification."""
        return {
            "id": "call_123",
            "function": {
                "name": "clarify",
                "arguments": json.dumps(
                    {
                        "questions": [
                            "Which specific HCM module do you want to export?",
                            "What format should the export be in?",
                        ]
                    }
                ),
            },
        }

    @staticmethod
    def web_search_response() -> dict:
        """Mock tool call for web search."""
        return {
            "id": "call_456",
            "function": {
                "name": "web_search",
                "arguments": json.dumps(
                    {"queries": ["HCM configuration export best practices"]}
                ),
            },
        }

    @staticmethod
    def task_block_search_response() -> dict:
        """Mock tool call for task block search."""
        return {
            "id": "call_789",
            "function": {
                "name": "task_block_search",
                "arguments": json.dumps({"queries": ["export configurations"]}),
            },
        }
