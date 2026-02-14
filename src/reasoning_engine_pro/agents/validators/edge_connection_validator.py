"""Edge connection validator — ensures workflow graph connectivity."""

from ...core.interfaces.validator import (
    IWorkflowValidator,
    ValidationContext,
    ValidationResult,
)
from ...core.schemas.workflow import Block, Edge, Workflow
from ...observability.logger import get_logger

logger = get_logger(__name__)


class EdgeConnectionValidator(IWorkflowValidator):
    """Ensures workflow graph connectivity.

    Non-blocking — produces warnings only. Fixes:
    - Missing Start block (adds one)
    - Blocks with no incoming edges (connects from Start)
    - Duplicate edges (deduplicates)
    - Self-loops (removes)
    """

    @property
    def name(self) -> str:
        return "edge_connection"

    @property
    def is_blocking(self) -> bool:
        return False

    async def validate(
        self, workflow: Workflow, context: ValidationContext
    ) -> ValidationResult:
        result = ValidationResult()

        blocks = list(workflow.workflow_json)
        edges = [e.model_dump() for e in workflow.edges]

        # Step 1: Ensure Start block exists
        blocks, edges = self._ensure_start_block(blocks, edges, result)

        # Step 2: Deduplicate edges
        edges = self._deduplicate_edges(edges, result)

        # Step 3: Remove self-loops
        edges = self._remove_self_loops(edges, result)

        # Step 4: Check for disconnected blocks
        self._check_disconnected(blocks, edges, result)

        # Build corrected Edge models
        edge_models = []
        for e in edges:
            try:
                edge_models.append(Edge.model_validate(e))
            except Exception:
                pass

        result.corrected_workflow = Workflow(
            workflow_json=blocks,
            edges=edge_models,
            job_name=workflow.job_name,
        )

        return result

    def _ensure_start_block(
        self,
        blocks: list[Block],
        edges: list[dict],
        result: ValidationResult,
    ) -> tuple[list[Block], list[dict]]:
        """Add a Start block if missing and connect it to entry-point blocks."""
        has_start = any(b.ActionCode == "Start" for b in blocks)
        if has_start:
            return blocks, edges

        result.add_warning("Start block was missing — added automatically")

        block_ids = {b.BlockId for b in blocks}
        start_id = "B000" if "B000" not in block_ids else "B999"

        start_block = Block(
            BlockId=start_id,
            Name="Start",
            ActionCode="Start",
            Inputs=[],
            Outputs=[],
        )
        blocks = [start_block] + blocks

        # Find blocks with no incoming edges
        targets_with_incoming = {e.get("To") for e in edges}
        entry_blocks = [
            b.BlockId for b in blocks
            if b.BlockId != start_id and b.BlockId not in targets_with_incoming
        ]

        max_edge_num = self._max_edge_num(edges)
        for bid in entry_blocks:
            max_edge_num += 1
            edges.append({
                "EdgeID": f"E{max_edge_num:03d}",
                "From": start_id,
                "To": bid,
            })

        return blocks, edges

    def _deduplicate_edges(
        self, edges: list[dict], result: ValidationResult
    ) -> list[dict]:
        """Remove duplicate edges (same From+To pair)."""
        seen: set[tuple[str, str]] = set()
        unique: list[dict] = []
        for e in edges:
            pair = (e.get("From", ""), e.get("To", ""))
            if pair in seen:
                result.add_warning(
                    f"Duplicate edge removed: {e.get('From')} -> {e.get('To')}"
                )
                continue
            seen.add(pair)
            unique.append(e)
        return unique

    def _remove_self_loops(
        self, edges: list[dict], result: ValidationResult
    ) -> list[dict]:
        """Remove edges where From == To."""
        clean: list[dict] = []
        for e in edges:
            if e.get("From") == e.get("To"):
                result.add_warning(f"Self-loop removed: {e.get('EdgeID', '?')}")
            else:
                clean.append(e)
        return clean

    def _check_disconnected(
        self,
        blocks: list[Block],
        edges: list[dict],
        result: ValidationResult,
    ) -> None:
        """Warn about blocks with no connections at all."""
        connected = set()
        for e in edges:
            connected.add(e.get("From"))
            connected.add(e.get("To"))

        for b in blocks:
            if b.ActionCode == "Start":
                continue
            if b.BlockId not in connected:
                result.add_warning(
                    f"Block {b.BlockId} ({b.Name}) has no edge connections"
                )

    @staticmethod
    def _max_edge_num(edges: list[dict]) -> int:
        """Get the highest edge number from existing edge IDs."""
        max_num = 0
        for e in edges:
            eid = e.get("EdgeID", "")
            if eid.startswith("E") and eid[1:].isdigit():
                max_num = max(max_num, int(eid[1:]))
        return max_num
