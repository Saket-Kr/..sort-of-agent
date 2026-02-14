"""Workflow structural validator."""

import re

from ..core.interfaces.event_emitter import IEventEmitter
from ..core.interfaces.validator import IWorkflowValidator, ValidationContext, ValidationResult
from ..core.schemas.workflow import Block, Workflow


class StructuralValidator(IWorkflowValidator):
    """Validates workflow structure and block references.

    This is the first stage in the validation pipeline — fast, deterministic,
    no LLM calls. Checks structural correctness: block IDs, edges, references,
    flow connectivity.
    """

    # Known action codes and their required inputs
    KNOWN_ACTIONS = {
        "Start": {"required_inputs": [], "required_outputs": []},
        "ExportConfigurations": {
            "required_inputs": ["Module"],
            "required_outputs": ["ConfigFile"],
        },
        "ImportData": {"required_inputs": ["DataFile"], "required_outputs": ["Result"]},
        "ValidateData": {
            "required_inputs": ["DataFile"],
            "required_outputs": ["ValidationResult"],
        },
        "AskWilfred": {"required_inputs": ["Question"], "required_outputs": ["Answer"]},
        "TransformData": {
            "required_inputs": ["Input"],
            "required_outputs": ["Output"],
        },
        "ConditionalBranch": {
            "required_inputs": ["Condition"],
            "required_outputs": [],
        },
    }

    def __init__(
        self,
        event_emitter: IEventEmitter | None = None,
        strict_mode: bool = False,
    ):
        self._event_emitter = event_emitter
        self._strict_mode = strict_mode

    @property
    def name(self) -> str:
        return "structural"

    @property
    def is_blocking(self) -> bool:
        return True

    async def validate(
        self,
        workflow: Workflow,
        context: ValidationContext | None = None,
    ) -> ValidationResult:
        """Validate workflow structure.

        Accepts either a ValidationContext (pipeline interface) or None
        for backward compatibility with the old call signature.
        """
        result = ValidationResult()

        conversation_id = context.conversation_id if context else None
        event_emitter = (
            context.event_emitter if context else self._event_emitter
        )

        total_steps = 5
        current_step = 0

        async def emit_progress(stage: str, message: str) -> None:
            if event_emitter and conversation_id:
                progress = (current_step / total_steps) * 100
                await event_emitter.emit_validation_progress(
                    conversation_id, stage, progress, message, result.errors
                )

        await emit_progress("structure", "Validating workflow structure...")
        self._validate_structure(workflow, result)
        current_step += 1

        await emit_progress("blocks", "Validating blocks...")
        self._validate_blocks(workflow, result)
        current_step += 1

        await emit_progress("edges", "Validating edges...")
        self._validate_edges(workflow, result)
        current_step += 1

        await emit_progress("references", "Validating output references...")
        self._validate_references(workflow, result)
        current_step += 1

        await emit_progress("flow", "Validating execution flow...")
        self._validate_flow(workflow, result)
        current_step += 1

        if self._strict_mode and result.warnings:
            result.errors.extend([f"Warning (strict): {w}" for w in result.warnings])

        await emit_progress("complete", "Validation complete")
        return result

    def _validate_structure(self, workflow: Workflow, result: ValidationResult) -> None:
        """Validate basic workflow structure."""
        if not workflow.workflow_json:
            result.add_error("Workflow must have at least one block")
            return

        if not workflow.edges and len(workflow.workflow_json) > 1:
            result.add_warning("Workflow has multiple blocks but no edges")

    def _validate_blocks(self, workflow: Workflow, result: ValidationResult) -> None:
        """Validate individual blocks."""
        block_ids = set()
        has_start = False

        for block in workflow.workflow_json:
            if block.BlockId in block_ids:
                result.add_error(f"Duplicate BlockId: {block.BlockId}")
            block_ids.add(block.BlockId)

            if not re.match(r"^B\d{3}$", block.BlockId):
                result.add_warning(
                    f"BlockId '{block.BlockId}' doesn't follow B### pattern"
                )

            if block.ActionCode == "Start":
                if has_start:
                    result.add_error("Multiple Start blocks found")
                has_start = True

            if not block.Name or not block.Name.strip():
                result.add_error(f"Block {block.BlockId} has empty name")

            if not block.ActionCode:
                result.add_error(f"Block {block.BlockId} has no ActionCode")

            self._validate_block_io(block, result)

        if not has_start:
            result.add_error("Workflow must have a Start block")

    def _validate_block_io(self, block: Block, result: ValidationResult) -> None:
        """Validate block inputs and outputs against known action requirements."""
        if block.ActionCode not in self.KNOWN_ACTIONS:
            return

        spec = self.KNOWN_ACTIONS[block.ActionCode]
        input_names = {inp.Name for inp in block.Inputs}

        for required in spec["required_inputs"]:
            if required not in input_names:
                result.add_warning(
                    f"Block {block.BlockId} ({block.ActionCode}) "
                    f"missing recommended input: {required}"
                )

    def _validate_edges(self, workflow: Workflow, result: ValidationResult) -> None:
        """Validate edges."""
        edge_ids = set()
        block_ids = {block.BlockId for block in workflow.workflow_json}

        for edge in workflow.edges:
            if edge.EdgeID in edge_ids:
                result.add_error(f"Duplicate EdgeID: {edge.EdgeID}")
            edge_ids.add(edge.EdgeID)

            if not re.match(r"^E\d{3}$", edge.EdgeID):
                result.add_warning(
                    f"EdgeID '{edge.EdgeID}' doesn't follow E### pattern"
                )

            if edge.From not in block_ids:
                result.add_error(
                    f"Edge {edge.EdgeID} references non-existent From block: {edge.From}"
                )

            if edge.To not in block_ids:
                result.add_error(
                    f"Edge {edge.EdgeID} references non-existent To block: {edge.To}"
                )

            if edge.From == edge.To:
                result.add_warning(f"Edge {edge.EdgeID} is a self-loop")

            if edge.EdgeCondition and edge.EdgeCondition not in ["true", "false"]:
                result.add_warning(
                    f"Edge {edge.EdgeID} has unusual condition: {edge.EdgeCondition}"
                )

    def _validate_references(
        self, workflow: Workflow, result: ValidationResult
    ) -> None:
        """Validate output variable references."""
        available_outputs = set()
        for block in workflow.workflow_json:
            for output in block.Outputs:
                available_outputs.add(output.OutputVariableName)

        for block in workflow.workflow_json:
            for inp in block.Inputs:
                if inp.ReferencedOutputVariableName:
                    if inp.ReferencedOutputVariableName not in available_outputs:
                        result.add_error(
                            f"Block {block.BlockId} references non-existent output: "
                            f"{inp.ReferencedOutputVariableName}"
                        )

    def _validate_flow(self, workflow: Workflow, result: ValidationResult) -> None:
        """Validate execution flow."""
        if not workflow.workflow_json:
            return

        block_ids = {block.BlockId for block in workflow.workflow_json}

        outgoing: dict[str, list[str]] = {bid: [] for bid in block_ids}
        incoming: dict[str, list[str]] = {bid: [] for bid in block_ids}

        for edge in workflow.edges:
            if edge.From in outgoing:
                outgoing[edge.From].append(edge.To)
            if edge.To in incoming:
                incoming[edge.To].append(edge.From)

        start_block = workflow.get_start_block()
        if not start_block:
            return

        if incoming.get(start_block.BlockId):
            result.add_error("Start block should not have incoming edges")

        reachable = {start_block.BlockId}
        queue = [start_block.BlockId]

        while queue:
            current = queue.pop(0)
            for next_block in outgoing.get(current, []):
                if next_block not in reachable:
                    reachable.add(next_block)
                    queue.append(next_block)

        unreachable = block_ids - reachable
        for block_id in unreachable:
            result.add_warning(f"Block {block_id} may be unreachable from Start")

        non_start_blocks = block_ids - {start_block.BlockId}
        for block_id in non_start_blocks:
            if not outgoing.get(block_id) and not incoming.get(block_id):
                result.add_warning(f"Block {block_id} is isolated (no edges)")

    def validate_sync(self, workflow: Workflow) -> ValidationResult:
        """Synchronous validation (for use in non-async contexts)."""
        result = ValidationResult()

        self._validate_structure(workflow, result)
        self._validate_blocks(workflow, result)
        self._validate_edges(workflow, result)
        self._validate_references(workflow, result)
        self._validate_flow(workflow, result)

        return result


# Backward-compat alias
WorkflowValidator = StructuralValidator
