"""Sample workflows for testing."""

from reasoning_engine_pro.core.schemas.workflow import (
    Block,
    Edge,
    Input,
    Output,
    Workflow,
)


class SampleWorkflows:
    """Collection of sample workflows for testing."""

    @staticmethod
    def simple_export() -> Workflow:
        """Simple export workflow."""
        return Workflow(
            workflow_json=[
                Block(
                    BlockId="B001",
                    Name="Start",
                    ActionCode="Start",
                    Inputs=[],
                    Outputs=[],
                ),
                Block(
                    BlockId="B002",
                    Name="Export Config",
                    ActionCode="ExportConfigurations",
                    Inputs=[
                        Input(Name="Module", StaticValue="HCM"),
                        Input(Name="Format", StaticValue="JSON"),
                    ],
                    Outputs=[
                        Output(
                            Name="ConfigFile", OutputVariableName="op-B002-ConfigFile"
                        ),
                    ],
                ),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
            ],
        )

    @staticmethod
    def import_with_validation() -> Workflow:
        """Import workflow with validation step."""
        return Workflow(
            workflow_json=[
                Block(
                    BlockId="B001",
                    Name="Start",
                    ActionCode="Start",
                    Inputs=[],
                    Outputs=[],
                ),
                Block(
                    BlockId="B002",
                    Name="Validate Input",
                    ActionCode="ValidateData",
                    Inputs=[
                        Input(Name="DataFile", StaticValue="input.csv"),
                    ],
                    Outputs=[
                        Output(
                            Name="ValidationResult",
                            OutputVariableName="op-B002-ValidationResult",
                        ),
                        Output(Name="IsValid", OutputVariableName="op-B002-IsValid"),
                    ],
                ),
                Block(
                    BlockId="B003",
                    Name="Import Data",
                    ActionCode="ImportData",
                    Inputs=[
                        Input(Name="DataFile", StaticValue="input.csv"),
                        Input(
                            Name="Validation",
                            ReferencedOutputVariableName="op-B002-ValidationResult",
                        ),
                    ],
                    Outputs=[
                        Output(
                            Name="ImportResult",
                            OutputVariableName="op-B003-ImportResult",
                        ),
                    ],
                ),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
                Edge(EdgeID="E002", From="B002", To="B003", EdgeCondition="true"),
            ],
        )

    @staticmethod
    def conditional_workflow() -> Workflow:
        """Workflow with conditional branching."""
        return Workflow(
            workflow_json=[
                Block(
                    BlockId="B001",
                    Name="Start",
                    ActionCode="Start",
                    Inputs=[],
                    Outputs=[],
                ),
                Block(
                    BlockId="B002",
                    Name="Check Condition",
                    ActionCode="ConditionalBranch",
                    Inputs=[
                        Input(Name="Condition", StaticValue="data.count > 0"),
                    ],
                    Outputs=[],
                ),
                Block(
                    BlockId="B003",
                    Name="Process Data",
                    ActionCode="TransformData",
                    Inputs=[],
                    Outputs=[],
                ),
                Block(
                    BlockId="B004",
                    Name="Skip Processing",
                    ActionCode="NotifyUser",
                    Inputs=[
                        Input(Name="Message", StaticValue="No data to process"),
                    ],
                    Outputs=[],
                ),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
                Edge(EdgeID="E002", From="B002", To="B003", EdgeCondition="true"),
                Edge(EdgeID="E003", From="B002", To="B004", EdgeCondition="false"),
            ],
        )

    @staticmethod
    def invalid_missing_start() -> Workflow:
        """Invalid workflow missing start block."""
        return Workflow(
            workflow_json=[
                Block(
                    BlockId="B001",
                    Name="Process",
                    ActionCode="ProcessData",
                    Inputs=[],
                    Outputs=[],
                ),
            ],
            edges=[],
        )

    @staticmethod
    def invalid_broken_reference() -> Workflow:
        """Invalid workflow with broken output reference."""
        return Workflow(
            workflow_json=[
                Block(
                    BlockId="B001",
                    Name="Start",
                    ActionCode="Start",
                    Inputs=[],
                    Outputs=[],
                ),
                Block(
                    BlockId="B002",
                    Name="Process",
                    ActionCode="ProcessData",
                    Inputs=[
                        Input(
                            Name="Data",
                            ReferencedOutputVariableName="op-B999-NonExistent",
                        ),
                    ],
                    Outputs=[],
                ),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
            ],
        )
