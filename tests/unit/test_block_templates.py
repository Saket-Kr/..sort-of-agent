"""Tests for block templates."""

from datetime import datetime

import pytest

from reasoning_engine_pro.core.schemas.block_templates import (
    AI_BLOCK_TEMPLATE,
    MANUAL_BLOCK_TEMPLATE,
    TASK_BLOCK_TEMPLATE,
    BlockTemplate,
    DiscoveryBlockProcessor,
    get_template_for_action,
)
from reasoning_engine_pro.core.schemas.workflow import Block, Input


class TestAIBlockTemplate:
    """Tests for the AskWilfred AI block template."""

    def test_action_code(self):
        assert AI_BLOCK_TEMPLATE.ActionCode == "AskWilfred"

    def test_creates_valid_block(self):
        block = AI_BLOCK_TEMPLATE.create_block("B002")
        assert isinstance(block, Block)
        assert block.BlockId == "B002"
        assert block.ActionCode == "AskWilfred"
        assert block.Name == "Ask Wilfred"

    def test_has_three_inputs(self):
        block = AI_BLOCK_TEMPLATE.create_block("B002")
        assert len(block.Inputs) == 3
        input_names = [i.Name for i in block.Inputs]
        assert "Prompt" in input_names
        assert "Attachment" in input_names
        assert "Output Format" in input_names

    def test_has_one_output(self):
        block = AI_BLOCK_TEMPLATE.create_block("B002")
        assert len(block.Outputs) == 1
        assert block.Outputs[0].Name == "Output"

    def test_output_variable_name_uses_block_id(self):
        block = AI_BLOCK_TEMPLATE.create_block("B005")
        assert block.Outputs[0].OutputVariableName == "op-B005-Output"


class TestManualBlockTemplate:
    """Tests for the HumanDependent manual block template."""

    def test_action_code(self):
        assert MANUAL_BLOCK_TEMPLATE.ActionCode == "HumanDependent"

    def test_creates_valid_block(self):
        block = MANUAL_BLOCK_TEMPLATE.create_block("B003")
        assert block.ActionCode == "HumanDependent"
        assert block.Name == "Human Dependable Manual Task"

    def test_has_correct_inputs(self):
        block = MANUAL_BLOCK_TEMPLATE.create_block("B003")
        input_names = [i.Name for i in block.Inputs]
        assert "Task Recipients" in input_names
        assert "Task" in input_names
        assert "Attachment" in input_names

    def test_task_recipients_default(self):
        block = MANUAL_BLOCK_TEMPLATE.create_block("B003")
        recipients = next(i for i in block.Inputs if i.Name == "Task Recipients")
        assert recipients.StaticValue == "<user>"


class TestTaskBlockTemplate:
    """Tests for the generic task block template."""

    def test_creates_valid_block(self):
        block = TASK_BLOCK_TEMPLATE.create_block("B004")
        assert block.BlockId == "B004"
        assert isinstance(block, Block)

    def test_name_override(self):
        block = TASK_BLOCK_TEMPLATE.create_block("B004", Name="Custom Name")
        assert block.Name == "Custom Name"

    def test_action_code_override(self):
        block = TASK_BLOCK_TEMPLATE.create_block(
            "B004", ActionCode="ExportConfigurations"
        )
        assert block.ActionCode == "ExportConfigurations"


class TestGetTemplateForAction:
    """Tests for action code lookup."""

    def test_ask_wilfred(self):
        template = get_template_for_action("AskWilfred")
        assert template is AI_BLOCK_TEMPLATE

    def test_human_dependent(self):
        template = get_template_for_action("HumanDependent")
        assert template is MANUAL_BLOCK_TEMPLATE

    def test_unknown_returns_none(self):
        assert get_template_for_action("UnknownAction") is None

    def test_task_block_not_in_lookup(self):
        # Task blocks are populated dynamically from search results, not looked up
        assert get_template_for_action("SendEmail") is None


class TestDiscoveryBlockProcessor:
    """Tests for CreateDiscoverySnapshot default filling."""

    def _make_discovery_block(self, **input_overrides: str) -> Block:
        defaults = {
            "Should use client utility": "null",
            "Application": "",
            "Start Date": "null",
            "End Date": "null",
            "Timezone": "",
            "Business Process": "Hire an Employee",
        }
        defaults.update(input_overrides)
        return Block(
            BlockId="B002",
            Name="Run Discovery",
            ActionCode="CreateDiscoverySnapshot",
            Inputs=[Input(Name=k, StaticValue=v) for k, v in defaults.items()],
            Outputs=[],
        )

    def test_fills_empty_dates(self):
        block = self._make_discovery_block()
        result = DiscoveryBlockProcessor.apply_defaults(block)
        start = next(i for i in result.Inputs if i.Name == "Start Date")
        end = next(i for i in result.Inputs if i.Name == "End Date")
        assert start.StaticValue is not None
        assert "11:59:59 PM" in start.StaticValue
        assert end.StaticValue is not None
        assert "11:59:59 PM" in end.StaticValue

    def test_preserves_existing_dates(self):
        block = self._make_discovery_block(**{"Start Date": "1/1/2025 11:59:59 PM"})
        result = DiscoveryBlockProcessor.apply_defaults(block)
        start = next(i for i in result.Inputs if i.Name == "Start Date")
        assert start.StaticValue == "1/1/2025 11:59:59 PM"

    def test_sets_application(self):
        block = self._make_discovery_block()
        result = DiscoveryBlockProcessor.apply_defaults(block)
        app = next(i for i in result.Inputs if i.Name == "Application")
        assert app.StaticValue == "OracleFusion"

    def test_sets_timezone(self):
        block = self._make_discovery_block()
        result = DiscoveryBlockProcessor.apply_defaults(block)
        tz = next(i for i in result.Inputs if i.Name == "Timezone")
        assert tz.StaticValue == "UTC"

    def test_sets_client_utility_false(self):
        block = self._make_discovery_block()
        result = DiscoveryBlockProcessor.apply_defaults(block)
        util = next(
            i for i in result.Inputs if i.Name == "Should use client utility"
        )
        assert util.StaticValue == "False"

    def test_preserves_business_process(self):
        block = self._make_discovery_block()
        result = DiscoveryBlockProcessor.apply_defaults(block)
        bp = next(i for i in result.Inputs if i.Name == "Business Process")
        assert bp.StaticValue == "Hire an Employee"
