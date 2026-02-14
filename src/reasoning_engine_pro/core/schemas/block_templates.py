"""Block templates for workflow generation.

Typed Pydantic models representing the predefined block types:
- AI Block (AskWilfred): LLM-powered block for AI queries during workflow execution.
- Manual Block (HumanDependent): Pauses workflow for human action.
- Task Block: Generic template populated from task block search results.

Also includes DiscoveryBlockProcessor for CreateDiscoverySnapshot special defaults.
"""

from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field

from .workflow import Block, Input, Output


class DataTypeSpec(BaseModel):
    """Data type specification for block input/output fields."""

    DataType: str = "String"
    DataFormat: Optional[str] = None
    LovValues: list[str] = Field(default_factory=list)
    fileTypesToSupport: list[str] = Field(default_factory=list)


class BlockInputTemplate(BaseModel):
    """Template for a block input field."""

    Name: str
    Description: str = ""
    StaticValue: Optional[str] = None
    ReferencedOutputVariableName: Optional[str] = None
    data_type: Optional[DataTypeSpec] = None


class BlockOutputTemplate(BaseModel):
    """Template for a block output field."""

    Name: str
    OutputVariableName: str = "null"
    Description: str = ""
    data_type: Optional[DataTypeSpec] = None


class BlockTemplate(BaseModel):
    """Template for generating workflow blocks."""

    ActionCode: str
    Name: str
    KeywordId: str = ""
    group_name: str = ""
    sub_group: str = ""
    isEnabled: bool = True
    default_inputs: list[BlockInputTemplate] = Field(default_factory=list)
    default_outputs: list[BlockOutputTemplate] = Field(default_factory=list)

    def create_block(self, block_id: str, **overrides: object) -> Block:
        """Create a Block instance from this template.

        Args:
            block_id: The BlockId to assign (e.g. "B002").
            **overrides: Override Name, ActionCode, or other Block fields.
        """
        inputs = [
            Input(
                Name=inp.Name,
                Description=inp.Description or None,
                StaticValue=inp.StaticValue,
                ReferencedOutputVariableName=inp.ReferencedOutputVariableName,
            )
            for inp in self.default_inputs
        ]

        outputs = [
            Output(
                Name=out.Name,
                OutputVariableName=out.OutputVariableName.replace(
                    "null", f"op-{block_id}-{out.Name.replace(' ', '')}"
                ),
                Description=out.Description or None,
            )
            for out in self.default_outputs
        ]

        return Block(
            BlockId=block_id,
            Name=str(overrides.get("Name", self.Name)),
            ActionCode=str(overrides.get("ActionCode", self.ActionCode)),
            Inputs=inputs,
            Outputs=outputs,
        )


# ---------------------------------------------------------------------------
# Predefined templates
# ---------------------------------------------------------------------------

AI_BLOCK_TEMPLATE = BlockTemplate(
    ActionCode="AskWilfred",
    Name="Ask Wilfred",
    KeywordId="67a4e14d-8da2-4179-a0aa-f23a561f5f3a",
    group_name="AskWilfred",
    sub_group="AskWilfred",
    default_inputs=[
        BlockInputTemplate(
            Name="Prompt",
            StaticValue="prompt",
            Description=(
                "Prompt to be asked by wilfred, this can contain the question "
                "to be asked, the output format that you need to give, please "
                "make sure to provide your own output format"
            ),
            data_type=DataTypeSpec(DataType="textarea"),
        ),
        BlockInputTemplate(
            Name="Attachment",
            StaticValue="input value",
            Description=(
                "Attachment to be provided by the user that will support the "
                "prompt, in case your wilfred requires an attachment to process "
                "the given prompt, that attachment can be provided here"
            ),
            data_type=DataTypeSpec(DataType="File"),
        ),
        BlockInputTemplate(
            Name="Output Format",
            StaticValue="<output format>",
            Description=(
                "Output Format to be asked by wilfred, Make sure to provide "
                "as detailed output format as possible to get correct output format"
            ),
            data_type=DataTypeSpec(
                DataType="String",
                LovValues=["", "HTML", "JSON", "Text"],
            ),
        ),
    ],
    default_outputs=[
        BlockOutputTemplate(Name="Output", OutputVariableName="null"),
    ],
)

MANUAL_BLOCK_TEMPLATE = BlockTemplate(
    ActionCode="HumanDependent",
    Name="Human Dependable Manual Task",
    KeywordId="62ddb2ce-1bad-48df-9e49-4eac80feb2f4",
    group_name="Opkey",
    sub_group="Manual_Process",
    default_inputs=[
        BlockInputTemplate(Name="Task Recipients", StaticValue="<user>"),
        BlockInputTemplate(
            Name="Task",
            StaticValue="<to be used if input is static>",
        ),
        BlockInputTemplate(
            Name="Attachment",
            StaticValue="<to be used if input is static>",
        ),
    ],
    default_outputs=[
        BlockOutputTemplate(
            Name="IsHumanDepenedable",
            Description="Is the given task human dependable",
            OutputVariableName="null",
        ),
    ],
)

TASK_BLOCK_TEMPLATE = BlockTemplate(
    ActionCode="SendEmail",
    Name="Send Email",
    group_name="Opkey",
    sub_group="Notify",
    default_inputs=[
        BlockInputTemplate(Name="Subject"),
        BlockInputTemplate(Name="Body"),
        BlockInputTemplate(Name="Email IDs"),
        BlockInputTemplate(Name="Attachment"),
    ],
    default_outputs=[
        BlockOutputTemplate(Name="Sent", OutputVariableName="null"),
    ],
)


def get_template_for_action(action_code: str) -> Optional[BlockTemplate]:
    """Return the matching predefined template for a given ActionCode, or None."""
    _action_template_map: dict[str, BlockTemplate] = {
        "AskWilfred": AI_BLOCK_TEMPLATE,
        "HumanDependent": MANUAL_BLOCK_TEMPLATE,
    }
    return _action_template_map.get(action_code)


class DiscoveryBlockProcessor:
    """Handles CreateDiscoverySnapshot special defaults (dates, timezone)."""

    @staticmethod
    def apply_defaults(block: Block) -> Block:
        """Fill in default dates, timezone, and application for discovery blocks.

        Only modifies inputs that are empty or set to "null".
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        date_format = "%-m/%-d/%Y 11:59:59 PM"

        for inp in block.Inputs:
            value = inp.StaticValue
            is_empty = not value or value == "null"

            if inp.Name == "Should use client utility" and is_empty:
                inp.StaticValue = "False"
            elif inp.Name == "Application":
                inp.StaticValue = "OracleFusion"
            elif inp.Name == "Start Date" and is_empty:
                inp.StaticValue = start_date.strftime(date_format)
            elif inp.Name == "End Date" and is_empty:
                inp.StaticValue = end_date.strftime(date_format)
            elif inp.Name == "Timezone":
                inp.StaticValue = "UTC"

        return block
