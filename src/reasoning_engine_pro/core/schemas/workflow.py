"""Workflow schema definitions."""

from typing import Optional

from pydantic import BaseModel, Field


class Input(BaseModel):
    """Input definition for a workflow block."""

    Name: str = Field(..., description="Input parameter name")
    ReferencedOutputVariableName: Optional[str] = Field(
        None,
        description="Reference to output from another block (e.g., 'op-B001-File')",
    )
    StaticValue: Optional[str] = Field(None, description="Static value for the input")
    Description: Optional[str] = Field(None, description="Description of the input")


class Output(BaseModel):
    """Output definition for a workflow block."""

    Name: str = Field(..., description="Output parameter name")
    OutputVariableName: str = Field(
        ..., description="Output variable name (pattern: 'op-{BlockId}-{Type}')"
    )
    Description: Optional[str] = Field(None, description="Description of the output")


class Block(BaseModel):
    """A single block in a workflow."""

    BlockId: str = Field(
        ..., description="Unique block identifier (pattern: B001, B002, ...)"
    )
    Name: str = Field(..., description="Human-readable block name")
    ActionCode: str = Field(
        ...,
        description="Action code (e.g., 'Start', 'ExportConfigurations', 'AskWilfred')",
    )
    Inputs: list[Input] = Field(default_factory=list, description="Block inputs")
    Outputs: list[Output] = Field(default_factory=list, description="Block outputs")


class Edge(BaseModel):
    """Connection between two blocks in a workflow."""

    EdgeID: str = Field(
        ..., description="Unique edge identifier (pattern: E001, E002, ...)"
    )
    From: str = Field(..., description="Source BlockId")
    To: str = Field(..., description="Target BlockId")
    EdgeCondition: Optional[str] = Field(
        None, description="Condition for conditional edges ('true' or 'false')"
    )


class Workflow(BaseModel):
    """Complete workflow definition."""

    workflow_json: list[Block] = Field(..., description="List of workflow blocks")
    edges: list[Edge] = Field(..., description="List of edges connecting blocks")
    job_name: Optional[str] = Field(
        None, description="Generated job name for the workflow"
    )

    def get_block_by_id(self, block_id: str) -> Block | None:
        """Get a block by its ID."""
        for block in self.workflow_json:
            if block.BlockId == block_id:
                return block
        return None

    def get_start_block(self) -> Block | None:
        """Get the start block of the workflow."""
        for block in self.workflow_json:
            if block.ActionCode == "Start":
                return block
        return None

    def get_outgoing_edges(self, block_id: str) -> list[Edge]:
        """Get all edges originating from a block."""
        return [edge for edge in self.edges if edge.From == block_id]

    def get_incoming_edges(self, block_id: str) -> list[Edge]:
        """Get all edges pointing to a block."""
        return [edge for edge in self.edges if edge.To == block_id]

    def validate_structure(self) -> list[str]:
        """Validate workflow structure and return list of errors."""
        errors: list[str] = []
        block_ids = {block.BlockId for block in self.workflow_json}

        # Check for start block
        start_blocks = [b for b in self.workflow_json if b.ActionCode == "Start"]
        if len(start_blocks) == 0:
            errors.append("Workflow must have a Start block")
        elif len(start_blocks) > 1:
            errors.append("Workflow must have exactly one Start block")

        # Validate edges reference existing blocks
        for edge in self.edges:
            if edge.From not in block_ids:
                errors.append(
                    f"Edge {edge.EdgeID} references non-existent block: {edge.From}"
                )
            if edge.To not in block_ids:
                errors.append(
                    f"Edge {edge.EdgeID} references non-existent block: {edge.To}"
                )

        # Validate output variable references in inputs
        output_vars = set()
        for block in self.workflow_json:
            for output in block.Outputs:
                output_vars.add(output.OutputVariableName)

        for block in self.workflow_json:
            for inp in block.Inputs:
                if inp.ReferencedOutputVariableName:
                    if inp.ReferencedOutputVariableName not in output_vars:
                        errors.append(
                            f"Block {block.BlockId} references non-existent output: "
                            f"{inp.ReferencedOutputVariableName}"
                        )

        return errors
