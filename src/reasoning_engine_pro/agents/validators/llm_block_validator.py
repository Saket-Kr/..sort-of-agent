"""LLM-based per-block validator with parallel execution."""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

from ...core.enums import MessageRole
from ...core.interfaces.llm_provider import ILLMProvider
from ...core.interfaces.validator import (
    IWorkflowValidator,
    ValidationContext,
    ValidationResult,
)
from ...core.schemas.block_templates import (
    AI_BLOCK_TEMPLATE,
    MANUAL_BLOCK_TEMPLATE,
    TASK_BLOCK_TEMPLATE,
    DiscoveryBlockProcessor,
)
from ...core.schemas.messages import ChatMessage
from ...core.schemas.workflow import Block, Edge, Input, Output, Workflow
from ...observability.logger import get_logger
from ...services.search.task_block import TaskBlockSearchService
from ..prompts.validator import get_validation_prompt

logger = get_logger(__name__)

_CUSTOM_ACTION_CODES = {"HumanDependent", "AskWilfred", "HumanDependable"}


@dataclass
class _BlockValidationResult:
    """Internal result from validating a single block."""

    index: int
    block: Block
    edges_to_add: list[dict]
    edges_to_remove: list[dict]


class LLMBlockValidator(IWorkflowValidator):
    """Per-block LLM validation with parallel execution.

    For each non-Start block:
    1. Searches for matching task blocks
    2. Sends block + search results to a validator LLM
    3. Parses LLM response for corrections
    4. Routes to task-block or custom-block processing
    """

    def __init__(
        self,
        llm_provider: ILLMProvider,
        search_service: TaskBlockSearchService,
        max_parallel: int = 5,
    ):
        self._llm = llm_provider
        self._search = search_service
        self._max_parallel = max_parallel

    @property
    def name(self) -> str:
        return "llm_block"

    @property
    def is_blocking(self) -> bool:
        return True

    async def validate(
        self, workflow: Workflow, context: ValidationContext
    ) -> ValidationResult:
        """Validate all non-Start blocks in parallel via LLM."""
        result = ValidationResult()
        blocks = workflow.workflow_json
        edges = workflow.edges

        if not blocks:
            return result

        # Prepare block dicts for the LLM prompt
        block_dicts = [b.model_dump() for b in blocks]
        edge_dicts = [e.model_dump() for e in edges]

        semaphore = asyncio.Semaphore(self._max_parallel)

        async def _validate_one(index: int) -> _BlockValidationResult:
            async with semaphore:
                return await self._validate_block(
                    index, blocks[index], block_dicts, edge_dicts, context
                )

        # Run all blocks in parallel
        tasks = [_validate_one(i) for i in range(len(blocks))]
        block_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        corrected_blocks: list[Block] = list(blocks)
        all_edges_to_add: list[dict] = []
        all_edges_to_remove: list[dict] = []

        for br in block_results:
            if isinstance(br, Exception):
                logger.error("Block validation error", error=str(br))
                result.add_warning(f"Block validation failed: {br}")
                continue
            corrected_blocks[br.index] = br.block
            all_edges_to_add.extend(br.edges_to_add)
            all_edges_to_remove.extend(br.edges_to_remove)

        # Post-process edges
        final_edges = self._post_process_edges(
            edge_dicts, all_edges_to_add, all_edges_to_remove
        )

        # Build corrected workflow
        corrected_edge_models = []
        for e in final_edges:
            try:
                corrected_edge_models.append(Edge.model_validate(e))
            except Exception:
                pass

        result.corrected_workflow = Workflow(
            workflow_json=corrected_blocks,
            edges=corrected_edge_models,
            job_name=workflow.job_name,
        )

        return result

    async def _validate_block(
        self,
        index: int,
        block: Block,
        all_block_dicts: list[dict],
        edge_dicts: list[dict],
        context: ValidationContext,
    ) -> _BlockValidationResult:
        """Validate a single block against the task block library."""
        # Skip Start blocks
        if block.ActionCode == "Start":
            return _BlockValidationResult(
                index=index, block=block, edges_to_add=[], edges_to_remove=[]
            )

        block_dict = block.model_dump()

        # 1. Search for matching task blocks
        task_block_results = await self._search_task_blocks(block)

        # 2. Check for exact action code match (fast path)
        exact_match = next(
            (tb for tb in task_block_results if tb["action_code"] == block.ActionCode),
            None,
        )

        # 3. Build prompt and call LLM
        prompt = get_validation_prompt(
            block=block_dict,
            task_block_results=task_block_results,
            workflow_blocks=all_block_dicts,
            user_query=context.user_query,
            edges=edge_dicts,
        )

        llm_response = await self._call_llm(prompt)
        parsed = self._parse_validation_response(llm_response, block_dict)

        edges_to_add = parsed["edges_to_add"]
        edges_to_remove = parsed["edges_to_remove"]

        # 4. Route based on LLM response
        if parsed["is_modified"] and parsed["block"]:
            corrected = parsed["block"]

            # Check if LLM's corrected block matches a task block
            corrected_action = corrected.get("ActionCode")
            matching_tb = next(
                (tb for tb in task_block_results if tb["action_code"] == corrected_action),
                None,
            )
            if matching_tb:
                final_block = self._process_task_block(corrected, matching_tb, block.BlockId)
            elif corrected.get("ActionCode") in _CUSTOM_ACTION_CODES:
                final_block = self._process_custom_block(corrected, block.BlockId)
            elif exact_match:
                # LLM gave an invalid ActionCode — fall back to exact match
                final_block = self._process_task_block(block_dict, exact_match, block.BlockId)
            else:
                final_block = self._ensure_block_structure(corrected, block.BlockId)
        else:
            # Not modified — process with original block
            if block.ActionCode in _CUSTOM_ACTION_CODES:
                final_block = self._process_custom_block(block_dict, block.BlockId)
            elif exact_match:
                final_block = self._process_task_block(block_dict, exact_match, block.BlockId)
            else:
                final_block = block

        # Emit progress
        if context.event_emitter:
            await context.event_emitter.emit_validation_progress(
                context.conversation_id,
                "llm_validation",
                0,
                f"Validated block {block.BlockId}: {block.Name}",
                message_id=context.message_id,
            )

        return _BlockValidationResult(
            index=index,
            block=final_block,
            edges_to_add=edges_to_add,
            edges_to_remove=edges_to_remove,
        )

    async def _search_task_blocks(self, block: Block) -> list[dict]:
        """Search for task blocks matching this block."""
        try:
            results = await self._search.search(block.Name or block.ActionCode)
            return [r.model_dump() for r in results]
        except Exception as e:
            logger.warning("Task block search failed", block_id=block.BlockId, error=str(e))
            return []

    async def _call_llm(self, prompt: str) -> str:
        """Call the validator LLM with a prompt. Non-streaming."""
        messages = [
            ChatMessage(role=MessageRole.USER, content=prompt),
        ]
        response = await self._llm.generate(
            messages=messages,
            temperature=0.3,
        )
        return response.content or ""

    def _parse_validation_response(
        self, response: str, original_block: dict
    ) -> dict[str, Any]:
        """Parse LLM validation response.

        Extracts:
        - is_modified: whether the block was changed
        - block: corrected block dict (or None)
        - edges_to_add: list of edge dicts
        - edges_to_remove: list of edge dicts
        """
        result: dict[str, Any] = {
            "is_modified": False,
            "block": None,
            "edges_to_add": [],
            "edges_to_remove": [],
        }

        # Always extract edge modifications (they can exist even with NO_CHANGES_NEEDED)
        add_match = re.search(r"Add:\s*(\[.*?\])", response, re.DOTALL)
        if add_match:
            try:
                result["edges_to_add"] = json.loads(add_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        remove_match = re.search(r"Remove:\s*(\[.*?\])", response, re.DOTALL)
        if remove_match:
            try:
                result["edges_to_remove"] = json.loads(remove_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Early returns for block-level no-change indicators
        if "NO MATCH - CUSTOM BLOCK" in response:
            return result

        if "NO_CHANGES_NEEDED" in response:
            return result

        # Extract corrected block JSON from code fences
        json_matches = re.findall(r"```json\s*([\s\S]*?)\s*```", response)
        if json_matches:
            try:
                corrected = json.loads(json_matches[-1])
                if corrected != original_block:
                    result["is_modified"] = True
                    result["block"] = corrected
            except json.JSONDecodeError:
                pass

        return result

    def _process_task_block(
        self, block_dict: dict, task_block: dict, block_id: str
    ) -> Block:
        """Map a block to a task block template using the task block definition."""
        template = TASK_BLOCK_TEMPLATE.create_block(block_id)
        block_data = template.model_dump()

        block_data["ActionCode"] = task_block["action_code"]
        block_data["Name"] = block_dict.get("Name", task_block.get("name", ""))

        # Map inputs from task block definition, preserving planner values
        llm_inputs = block_dict.get("Inputs", block_dict.get("inputs", []))
        mapped_inputs = []
        for tb_input in task_block.get("inputs", []):
            input_name = tb_input.get("name", tb_input.get("Name", ""))
            # Find matching input from the planner's block
            llm_match = next(
                (
                    i for i in llm_inputs
                    if isinstance(i, dict) and
                    (i.get("Name") == input_name or i.get("name") == input_name)
                ),
                {},
            )
            mapped_inputs.append(
                Input(
                    Name=input_name,
                    StaticValue=llm_match.get("StaticValue"),
                    ReferencedOutputVariableName=llm_match.get("ReferencedOutputVariableName"),
                    Description=tb_input.get("description", ""),
                )
            )

        # Map outputs from task block definition
        llm_outputs = block_dict.get("Outputs", block_dict.get("outputs", []))
        mapped_outputs = []
        for tb_output in task_block.get("outputs", []):
            output_name = tb_output.get("name", tb_output.get("Name", ""))
            llm_match = next(
                (
                    o for o in llm_outputs
                    if isinstance(o, dict) and
                    (o.get("Name") == output_name or o.get("name") == output_name)
                ),
                None,
            )
            if not llm_match and llm_outputs:
                llm_match = llm_outputs[0] if isinstance(llm_outputs[0], dict) else {}
            elif not llm_match:
                llm_match = {}

            default_var = f"op-{block_id}-{output_name}"
            mapped_outputs.append(
                Output(
                    Name=output_name,
                    OutputVariableName=llm_match.get("OutputVariableName", default_var),
                    Description=tb_output.get("description", ""),
                )
            )

        result = Block(
            BlockId=block_id,
            ActionCode=task_block["action_code"],
            Name=block_data["Name"],
            Inputs=mapped_inputs,
            Outputs=mapped_outputs,
        )

        # Special case: CreateDiscoverySnapshot
        if result.ActionCode == "CreateDiscoverySnapshot":
            result = DiscoveryBlockProcessor.apply_defaults(result)

        return result

    def _process_custom_block(self, block_dict: dict, block_id: str) -> Block:
        """Process an AI or Manual custom block using templates."""
        action_code = block_dict.get("ActionCode", "")
        inputs_list = block_dict.get("Inputs", block_dict.get("inputs", []))
        outputs_list = block_dict.get("Outputs", block_dict.get("outputs", []))

        def _get_input_value(name: str) -> str:
            return next(
                (
                    i.get("StaticValue", "") or ""
                    for i in inputs_list
                    if isinstance(i, dict) and (i.get("Name") == name or i.get("name") == name)
                ),
                "",
            )

        def _get_input_ref(name: str) -> str:
            return next(
                (
                    i.get("ReferencedOutputVariableName", "") or ""
                    for i in inputs_list
                    if isinstance(i, dict) and (i.get("Name") == name or i.get("name") == name)
                ),
                "",
            )

        if action_code in ("HumanDependent", "HumanDependable"):
            template = MANUAL_BLOCK_TEMPLATE.create_block(block_id)
            template_inputs = [
                Input(Name="Task Recipients", StaticValue=_get_input_value("Task Recipients")),
                Input(Name="Task", StaticValue=_get_input_value("Task")),
                Input(Name="Attachment", StaticValue=_get_input_value("Attachment")),
            ]
            template = template.model_copy(update={
                "ActionCode": "HumanDependent",
                "Name": block_dict.get("Name", "Manual Task"),
                "Inputs": template_inputs,
            })
        elif action_code == "AskWilfred":
            template = AI_BLOCK_TEMPLATE.create_block(block_id)
            template_inputs = [
                Input(Name="Prompt", StaticValue=_get_input_value("Prompt")),
                Input(
                    Name="Attachment",
                    StaticValue=_get_input_value("Attachment"),
                    ReferencedOutputVariableName=_get_input_ref("Attachment") or None,
                ),
                Input(
                    Name="Output Format",
                    StaticValue=_get_input_value("Output Format"),
                    ReferencedOutputVariableName=_get_input_ref("Output Format") or None,
                ),
            ]
            template = template.model_copy(update={
                "Name": block_dict.get("Name", "Ask Wilfred"),
                "Inputs": template_inputs,
            })
        else:
            return self._ensure_block_structure(block_dict, block_id)

        # Map outputs from original block
        mapped_outputs = []
        for o in outputs_list:
            if isinstance(o, dict):
                mapped_outputs.append(
                    Output(
                        Name=o.get("Name", o.get("name", "Output")),
                        OutputVariableName=o.get("OutputVariableName", f"op-{block_id}-Output"),
                        Description=o.get("Description", ""),
                    )
                )
        if not mapped_outputs:
            mapped_outputs = [Output(Name="Output", OutputVariableName=f"op-{block_id}-Output")]

        template = template.model_copy(update={"Outputs": mapped_outputs})
        return template

    def _ensure_block_structure(self, block_dict: dict, block_id: str) -> Block:
        """Ensure a block dict has all required fields and return a valid Block."""
        # Normalize field names
        inputs_raw = block_dict.get("Inputs", block_dict.get("inputs", []))
        outputs_raw = block_dict.get("Outputs", block_dict.get("outputs", []))

        inputs = []
        for i in inputs_raw:
            if isinstance(i, dict):
                inputs.append(Input(
                    Name=i.get("Name", i.get("name", "Input")),
                    StaticValue=i.get("StaticValue"),
                    ReferencedOutputVariableName=i.get("ReferencedOutputVariableName"),
                    Description=i.get("Description"),
                ))

        outputs = []
        for o in outputs_raw:
            if isinstance(o, dict):
                outputs.append(Output(
                    Name=o.get("Name", o.get("name", "Output")),
                    OutputVariableName=o.get("OutputVariableName", f"op-{block_id}-Output"),
                    Description=o.get("Description"),
                ))

        action_code = block_dict.get("ActionCode", block_dict.get("action_code", ""))
        if not action_code:
            # No action code — fall back to AI block
            return AI_BLOCK_TEMPLATE.create_block(block_id)

        return Block(
            BlockId=block_id,
            ActionCode=action_code,
            Name=block_dict.get("Name", block_dict.get("name", "Unnamed Block")),
            Inputs=inputs,
            Outputs=outputs,
        )

    def _post_process_edges(
        self,
        original_edges: list[dict],
        edges_to_add: list[dict],
        edges_to_remove: list[dict],
    ) -> list[dict]:
        """Post-process edges: deduplicate, remove self-loops, apply additions/removals."""
        # Remove self-loops from original edges
        edges = [e for e in original_edges if e.get("From") != e.get("To")]

        # Remove edges marked for removal
        remove_set = {
            (e.get("From", ""), e.get("To", "")) for e in edges_to_remove
        }
        edges = [e for e in edges if (e.get("From"), e.get("To")) not in remove_set]

        # Calculate next edge ID
        max_edge_num = 0
        for e in edges:
            edge_id = e.get("EdgeID", "")
            if edge_id.startswith("E") and edge_id[1:].isdigit():
                max_edge_num = max(max_edge_num, int(edge_id[1:]))

        # Deduplicate and add new edges
        existing_pairs = {(e.get("From"), e.get("To")) for e in edges}
        for new_edge in edges_to_add:
            pair = (new_edge.get("From"), new_edge.get("To"))
            if pair in existing_pairs:
                continue
            if pair[0] == pair[1]:
                continue  # Skip self-loops

            max_edge_num += 1
            edge_id = f"E{max_edge_num:03d}"
            edges.append({
                "EdgeID": edge_id,
                "From": new_edge["From"],
                "To": new_edge["To"],
            })
            existing_pairs.add(pair)

        return edges
