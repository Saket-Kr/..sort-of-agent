"""Tests for validation interface, pipeline, and individual validators."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reasoning_engine_pro.core.enums import MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage
from reasoning_engine_pro.agents.validator import StructuralValidator, WorkflowValidator
from reasoning_engine_pro.agents.validators.edge_connection_validator import (
    EdgeConnectionValidator,
)
from reasoning_engine_pro.agents.validators.llm_block_validator import LLMBlockValidator
from reasoning_engine_pro.agents.validators.pipeline import ValidationPipeline
from reasoning_engine_pro.core.interfaces.validator import (
    IWorkflowValidator,
    ValidationContext,
    ValidationResult,
)
from reasoning_engine_pro.core.schemas.workflow import (
    Block,
    Edge,
    Input,
    Output,
    Workflow,
)
from tests.fixtures.sample_workflows import SampleWorkflows


def _make_context(conversation_id: str = "test-conv") -> ValidationContext:
    return ValidationContext(
        conversation_id=conversation_id,
        user_query="Export HCM configuration",
    )


# ---- StructuralValidator ----


class TestStructuralValidator:
    """Tests for the refactored StructuralValidator (IWorkflowValidator interface)."""

    @pytest.fixture
    def validator(self):
        return StructuralValidator()

    def test_implements_interface(self, validator):
        assert isinstance(validator, IWorkflowValidator)

    def test_name_and_blocking(self, validator):
        assert validator.name == "structural"
        assert validator.is_blocking is True

    def test_backward_compat_alias(self):
        assert WorkflowValidator is StructuralValidator

    @pytest.mark.asyncio
    async def test_valid_workflow(self, validator):
        workflow = SampleWorkflows.simple_export()
        result = await validator.validate(workflow, _make_context())
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_valid_without_context(self, validator):
        """Backward compat — validate with None context still works."""
        workflow = SampleWorkflows.simple_export()
        result = await validator.validate(workflow, None)
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_missing_start_block(self, validator):
        workflow = SampleWorkflows.invalid_missing_start()
        result = await validator.validate(workflow, _make_context())
        assert not result.is_valid
        assert any("Start" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_broken_reference(self, validator):
        workflow = SampleWorkflows.invalid_broken_reference()
        result = await validator.validate(workflow, _make_context())
        assert any("op-B999" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_duplicate_block_id(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B001", Name="Dup", ActionCode="ProcessData"),
            ],
            edges=[],
        )
        result = await validator.validate(workflow, _make_context())
        assert any("Duplicate BlockId" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_invalid_edge_reference(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B999"),
            ],
        )
        result = await validator.validate(workflow, _make_context())
        assert any("B999" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_strict_mode_promotes_warnings(self):
        validator = StructuralValidator(strict_mode=True)
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="Process", ActionCode="ProcessData"),
            ],
            edges=[],  # Multiple blocks, no edges → warning
        )
        result = await validator.validate(workflow, _make_context())
        assert any("strict" in e.lower() for e in result.errors)

    def test_validate_sync(self, validator):
        workflow = SampleWorkflows.simple_export()
        result = validator.validate_sync(workflow)
        assert result.is_valid


# ---- ValidationResult ----


class TestValidationResult:
    def test_merge(self):
        r1 = ValidationResult(errors=["e1"], warnings=["w1"])
        r2 = ValidationResult(errors=["e2"], warnings=["w2"])
        r1.merge(r2)
        assert r1.errors == ["e1", "e2"]
        assert r1.warnings == ["w1", "w2"]

    def test_merge_with_corrected_workflow(self):
        workflow = SampleWorkflows.simple_export()
        r1 = ValidationResult()
        r2 = ValidationResult(corrected_workflow=workflow)
        r1.merge(r2)
        assert r1.corrected_workflow is workflow

    def test_is_valid(self):
        assert ValidationResult().is_valid
        assert not ValidationResult(errors=["oops"]).is_valid


# ---- EdgeConnectionValidator ----


class TestEdgeConnectionValidator:
    @pytest.fixture
    def validator(self):
        return EdgeConnectionValidator()

    def test_name_and_non_blocking(self, validator):
        assert validator.name == "edge_connection"
        assert validator.is_blocking is False

    @pytest.mark.asyncio
    async def test_adds_start_block_when_missing(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B002", Name="Export", ActionCode="ExportConfigurations"),
            ],
            edges=[],
        )
        result = await validator.validate(workflow, _make_context())
        assert result.corrected_workflow is not None
        blocks = result.corrected_workflow.workflow_json
        start = [b for b in blocks if b.ActionCode == "Start"]
        assert len(start) == 1
        assert any("Start block was missing" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_connects_start_to_entry_blocks(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B002", Name="A", ActionCode="ActionA"),
                Block(BlockId="B003", Name="B", ActionCode="ActionB"),
            ],
            edges=[],
        )
        result = await validator.validate(workflow, _make_context())
        corrected = result.corrected_workflow
        # Start block added + edges to B002 and B003
        start_block = [b for b in corrected.workflow_json if b.ActionCode == "Start"][0]
        outgoing = [e for e in corrected.edges if e.From == start_block.BlockId]
        assert len(outgoing) == 2

    @pytest.mark.asyncio
    async def test_deduplicates_edges(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="Export", ActionCode="ExportConfigurations"),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
                Edge(EdgeID="E002", From="B001", To="B002"),  # Duplicate
            ],
        )
        result = await validator.validate(workflow, _make_context())
        assert len(result.corrected_workflow.edges) == 1
        assert any("Duplicate" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_removes_self_loops(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="Loop", ActionCode="LoopAction"),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
                Edge(EdgeID="E002", From="B002", To="B002"),  # Self-loop
            ],
        )
        result = await validator.validate(workflow, _make_context())
        assert len(result.corrected_workflow.edges) == 1
        assert any("Self-loop" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_warns_disconnected_blocks(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="Connected", ActionCode="ActionA"),
                Block(BlockId="B003", Name="Isolated", ActionCode="ActionB"),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
            ],
        )
        result = await validator.validate(workflow, _make_context())
        assert any("B003" in w and "no edge" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_preserves_valid_workflow(self, validator):
        workflow = SampleWorkflows.simple_export()
        result = await validator.validate(workflow, _make_context())
        assert result.corrected_workflow is not None
        assert len(result.corrected_workflow.workflow_json) == len(
            workflow.workflow_json
        )
        assert result.warnings == []


# ---- LLMBlockValidator ----


class TestLLMBlockValidator:
    @pytest.fixture
    def mock_search(self):
        service = AsyncMock(spec=["search"])
        service.search = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def mock_llm(self, mock_llm_provider):
        return mock_llm_provider

    @pytest.fixture
    def validator(self, mock_llm, mock_search):
        return LLMBlockValidator(
            llm_provider=mock_llm,
            search_service=mock_search,
            max_parallel=2,
        )

    def test_name_and_blocking(self, validator):
        assert validator.name == "llm_block"
        assert validator.is_blocking is True

    @pytest.mark.asyncio
    async def test_skips_start_block(self, validator):
        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
            ],
            edges=[],
        )
        result = await validator.validate(workflow, _make_context())
        assert result.is_valid
        assert result.corrected_workflow.workflow_json[0].ActionCode == "Start"

    @pytest.mark.asyncio
    async def test_handles_no_changes_response(self, validator, mock_llm):
        """LLM returns NO_CHANGES_NEEDED — block remains unchanged."""
        async def _generate(messages, **kwargs):
            return ChatMessage(
                role="assistant",
                content="NO_CHANGES_NEEDED",
            )

        mock_llm.generate = _generate

        workflow = SampleWorkflows.simple_export()
        result = await validator.validate(workflow, _make_context())
        assert result.is_valid
        assert result.corrected_workflow is not None

    @pytest.mark.asyncio
    async def test_corrects_block_from_llm_response(self, validator, mock_llm, mock_search):
        """LLM returns a corrected block JSON — validator applies it."""
        from reasoning_engine_pro.core.schemas.tools import TaskBlockSearchResult

        # Mock search returns a matching task block
        mock_search.search = AsyncMock(return_value=[
            TaskBlockSearchResult(
                block_id="tb-001",
                name="Export Config",
                action_code="ExportConfigs",
                inputs=[{"name": "Module", "data_type": {}}],
                outputs=[{"name": "ConfigFile"}],
                relevance_score=0.95,
            ),
        ])

        corrected_block = {
            "BlockId": "B002",
            "ActionCode": "ExportConfigs",
            "Name": "Export Config",
            "Inputs": [{"Name": "Module", "StaticValue": "HCM"}],
            "Outputs": [{"Name": "ConfigFile", "OutputVariableName": "op-B002-ConfigFile"}],
        }

        async def _generate(messages, **kwargs):
            return ChatMessage(
                role="assistant",
                content=f"Match Status: MATCH FOUND\n\nEdges:\nAdd: []\nRemove: []\n\nCorrected Block:\n```json\n{json.dumps(corrected_block)}\n```",
            )

        mock_llm.generate = _generate

        workflow = SampleWorkflows.simple_export()
        result = await validator.validate(workflow, _make_context())
        assert result.is_valid
        assert result.corrected_workflow is not None
        # Second block should have corrected ActionCode
        b2 = result.corrected_workflow.workflow_json[1]
        assert b2.ActionCode == "ExportConfigs"

    @pytest.mark.asyncio
    async def test_handles_custom_block_response(self, validator, mock_llm):
        """LLM indicates custom block (AskWilfred) — handled correctly."""
        corrected = {
            "BlockId": "B002",
            "ActionCode": "AskWilfred",
            "Name": "Ask AI",
            "Inputs": [
                {"Name": "Prompt", "StaticValue": "Help me"},
                {"Name": "Attachment", "StaticValue": ""},
                {"Name": "Output Format", "StaticValue": ""},
            ],
            "Outputs": [{"Name": "Output", "OutputVariableName": "op-B002-Output"}],
        }

        async def _generate(messages, **kwargs):
            return ChatMessage(
                role="assistant",
                content=f"Match Status: MATCH FOUND\n\nEdges:\nAdd: []\nRemove: []\n\n```json\n{json.dumps(corrected)}\n```",
            )

        mock_llm.generate = _generate

        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="Ask AI", ActionCode="AskWilfred"),
            ],
            edges=[Edge(EdgeID="E001", From="B001", To="B002")],
        )
        result = await validator.validate(workflow, _make_context())
        assert result.is_valid
        b2 = result.corrected_workflow.workflow_json[1]
        assert b2.ActionCode == "AskWilfred"

    @pytest.mark.asyncio
    async def test_edge_modifications(self, validator, mock_llm):
        """LLM suggests adding and removing edges."""
        async def _generate(messages, **kwargs):
            return ChatMessage(
                role="assistant",
                content=(
                    'Edges:\n'
                    'Add: [{"From": "B001", "To": "B003"}]\n'
                    'Remove: [{"From": "B001", "To": "B002"}]\n\n'
                    'NO_CHANGES_NEEDED'
                ),
            )

        mock_llm.generate = _generate

        workflow = Workflow(
            workflow_json=[
                Block(BlockId="B001", Name="Start", ActionCode="Start"),
                Block(BlockId="B002", Name="A", ActionCode="ActionA"),
                Block(BlockId="B003", Name="B", ActionCode="ActionB"),
            ],
            edges=[
                Edge(EdgeID="E001", From="B001", To="B002"),
            ],
        )
        result = await validator.validate(workflow, _make_context())
        corrected = result.corrected_workflow
        edge_pairs = [(e.From, e.To) for e in corrected.edges]
        assert ("B001", "B003") in edge_pairs
        # Original edge B001->B002 should be removed
        assert ("B001", "B002") not in edge_pairs

    @pytest.mark.asyncio
    async def test_llm_failure_returns_warnings(self, validator, mock_llm):
        """LLM throws an exception — block is unchanged, warning added."""
        async def _generate(messages, **kwargs):
            raise RuntimeError("LLM failed")

        mock_llm.generate = _generate

        workflow = SampleWorkflows.simple_export()
        result = await validator.validate(workflow, _make_context())
        # Non-Start block should have a warning about failure
        assert len(result.warnings) > 0


# ---- Response Parsing ----


class TestResponseParsing:
    @pytest.fixture
    def validator(self, mock_llm_provider):
        search = AsyncMock(spec=["search"])
        return LLMBlockValidator(
            llm_provider=mock_llm_provider,
            search_service=search,
        )

    def test_parse_no_changes(self, validator):
        result = validator._parse_validation_response("NO_CHANGES_NEEDED", {"BlockId": "B001"})
        assert not result["is_modified"]
        assert result["block"] is None

    def test_parse_custom_block(self, validator):
        result = validator._parse_validation_response("NO MATCH - CUSTOM BLOCK", {"BlockId": "B001"})
        assert not result["is_modified"]

    def test_parse_edges_to_add(self, validator):
        response = 'Add: [{"From": "B001", "To": "B003"}]\nRemove: []'
        result = validator._parse_validation_response(response, {"BlockId": "B001"})
        assert len(result["edges_to_add"]) == 1
        assert result["edges_to_add"][0]["From"] == "B001"

    def test_parse_corrected_block(self, validator):
        block = {"BlockId": "B002", "ActionCode": "NewAction", "Name": "New"}
        response = f"Corrected:\n```json\n{json.dumps(block)}\n```"
        result = validator._parse_validation_response(response, {"BlockId": "B002", "ActionCode": "OldAction"})
        assert result["is_modified"]
        assert result["block"]["ActionCode"] == "NewAction"

    def test_parse_same_block_not_modified(self, validator):
        block = {"BlockId": "B002", "ActionCode": "Same"}
        response = f"```json\n{json.dumps(block)}\n```"
        result = validator._parse_validation_response(response, block)
        assert not result["is_modified"]


# ---- Pipeline ----


class TestValidationPipeline:
    @pytest.mark.asyncio
    async def test_runs_stages_in_order(self):
        call_order = []

        class StageA(IWorkflowValidator):
            name = "a"
            is_blocking = True

            async def validate(self, workflow, context):
                call_order.append("a")
                return ValidationResult()

        class StageB(IWorkflowValidator):
            name = "b"
            is_blocking = False

            async def validate(self, workflow, context):
                call_order.append("b")
                return ValidationResult()

        pipeline = ValidationPipeline().add(StageA()).add(StageB())
        result = await pipeline.validate(SampleWorkflows.simple_export(), _make_context())
        assert call_order == ["a", "b"]
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_stops_on_blocking_failure(self):
        class FailingStage(IWorkflowValidator):
            name = "failing"
            is_blocking = True

            async def validate(self, workflow, context):
                return ValidationResult(errors=["critical failure"])

        class NeverReached(IWorkflowValidator):
            name = "never"
            is_blocking = False

            async def validate(self, workflow, context):
                raise AssertionError("Should not be reached")

        pipeline = ValidationPipeline().add(FailingStage()).add(NeverReached())
        result = await pipeline.validate(SampleWorkflows.simple_export(), _make_context())
        assert not result.is_valid
        assert "critical failure" in result.errors

    @pytest.mark.asyncio
    async def test_non_blocking_errors_dont_stop(self):
        class WarnStage(IWorkflowValidator):
            name = "warn"
            is_blocking = False

            async def validate(self, workflow, context):
                r = ValidationResult()
                r.add_warning("something fishy")
                return r

        class FinalStage(IWorkflowValidator):
            name = "final"
            is_blocking = False

            async def validate(self, workflow, context):
                return ValidationResult()

        pipeline = ValidationPipeline().add(WarnStage()).add(FinalStage())
        result = await pipeline.validate(SampleWorkflows.simple_export(), _make_context())
        assert result.is_valid
        assert "something fishy" in result.warnings

    @pytest.mark.asyncio
    async def test_corrected_workflow_threads_through(self):
        """Stage 1 corrects workflow, stage 2 sees the corrected version."""
        corrected = SampleWorkflows.import_with_validation()
        original = SampleWorkflows.simple_export()

        class Corrector(IWorkflowValidator):
            name = "corrector"
            is_blocking = False

            async def validate(self, workflow, context):
                r = ValidationResult()
                r.corrected_workflow = corrected
                return r

        class Checker(IWorkflowValidator):
            name = "checker"
            is_blocking = False
            seen_workflow = None

            async def validate(self, workflow, context):
                Checker.seen_workflow = workflow
                return ValidationResult()

        pipeline = ValidationPipeline().add(Corrector()).add(Checker())
        result = await pipeline.validate(original, _make_context())
        # Checker should have seen the corrected workflow
        assert Checker.seen_workflow is corrected
        # Final result should carry the corrected workflow
        assert result.corrected_workflow is corrected

    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        pipeline = ValidationPipeline()
        result = await pipeline.validate(SampleWorkflows.simple_export(), _make_context())
        assert result.is_valid

    def test_add_returns_self(self):
        class Dummy(IWorkflowValidator):
            name = "d"
            is_blocking = False
            async def validate(self, w, c):
                return ValidationResult()

        pipeline = ValidationPipeline()
        ret = pipeline.add(Dummy())
        assert ret is pipeline
