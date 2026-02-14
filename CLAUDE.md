# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reasoning Engine Pro is an agentic workflow planning system that uses LLMs with native function calling to generate enterprise automation workflows. It combines a FastAPI backend (WebSocket + REST), a vanilla JS web client, Redis storage, and OpenAI-compatible LLM providers (vLLM or OpenAI).

- **Status**: Under active development. Correctness and clarity over speed. No speculative changes unless explicitly requested.
- **Tech**: Python 3.11+, pyproject.toml for deps, Docker/docker-compose, pytest

## Common Commands

```bash
pip install -e ".[dev]"                           # install (dev mode)
python -m reasoning_engine_pro.main               # run server (default port 8765)

pytest                                            # all tests
pytest tests/unit/                                # unit tests only
pytest tests/integration/                         # integration tests only
pytest tests/unit/test_planner.py -k "test_name"  # single test
pytest --cov=reasoning_engine_pro                 # with coverage

ruff check src/                                   # lint
mypy src/                                         # type check

docker-compose up -d                              # run via docker
```

## Architecture

### Layered Design

```
Web Client (vanilla JS, no build step) → served from /app
    ↕ WebSocket + REST
FastAPI API Layer (api/) — thin routers, no business logic
    ↓
Agents Layer: Orchestrator → PlannerAgent → Validator → JobNameGenerator
    ↓
Core Layer: Schemas (Pydantic), Interfaces (ABCs), Enums, Exceptions
    ↓
Services: LLM Providers, Tool Executors, Storage, Search
```

### Request Flow

1. Client sends `start_chat` via WebSocket → `WebSocketHandler`
2. `ConversationOrchestrator` manages state machine, calls `PlannerAgent.plan()`
3. PlannerAgent runs an async LLM loop (max 10 iterations) with tool calling
4. Available tools: `web_search`, `task_block_search`, `clarify` (asks user questions)
5. Tool results feed back into LLM for next iteration
6. LLM produces workflow JSON → `WorkflowValidator` validates → `JobNameGenerator` names → emitted to client

### Key Abstractions

- **`ILLMProvider`** (`core/interfaces/`) — Strategy pattern for swappable LLM backends. Implementations: `VLLMProvider`, `OpenAIProvider`
- **`IToolExecutor[TInput, TOutput]`** — Generic typed interface for tools. Implementations: `WebSearchExecutor`, `TaskBlockSearchExecutor`, `ClarifyExecutor`
- **`IConversationStorage`** — Storage abstraction. Implementations: `RedisStorage` (persistent w/ TTL), `InMemoryStorage` (testing)
- **`IEventEmitter`** — Observer pattern for streaming events to WebSocket clients
- **`Dependencies`** (`api/dependencies.py`) — Singleton DI container wiring everything together

### Exception Hierarchy

All custom exceptions inherit from `ReasoningEngineError` in `core/exceptions.py`. Agents catch exceptions, the orchestrator logs and emits error events to clients, setting conversation status to ERROR.

### WebSocket Event Protocol

Client→Server: `start_chat`, `provide_clarification`, `end_chat`, `ping`, `input_analysis`
Server→Client: `stream_response`, `clarification_requested`, `opkey_workflow_json`, `validator_progress_update`, `error`, `web_search_started/results`, `task_block_search_started/results`

## Code Standards

Follow SOLID principles strictly. The codebase is structured for single-responsibility and separation of concerns:

- **One file, one responsibility.** Each file should own exactly one class, one schema group, or one logical unit. Don't combine unrelated concerns.
- **Schemas in `core/schemas/`.** All Pydantic models live here, grouped by domain (workflow, messages, events). Never define schemas inline in routers or services.
- **Thin routers.** API route files (`api/rest/`, `api/websocket/`) handle only request parsing, response formatting, and delegation. All business logic lives in agents or services.
- **Interfaces before implementations.** Define ABCs in `core/interfaces/` first. Implementations go in their own modules (`llm/providers/`, `tools/executors/`, `services/storage/`).
- **Factories for instantiation.** Use factory classes (`LLMProviderFactory`, `ToolFactory`) for creating implementations — never hard-code concrete classes at call sites.
- **Explicit over clever.** Prefer readable, straightforward implementations over abstractions that obscure intent.
- **Follow existing patterns.** Match the conventions already in the codebase. Do not refactor unrelated code.
- **No new dependencies** without explicit approval.

## Testing

- Unit tests mock dependencies; integration tests use `fakeredis` and FastAPI `TestClient`
- Shared fixtures in `tests/conftest.py`: `test_settings`, `memory_storage`, `sample_workflow`, `mock_llm_provider`, `test_client`
- Async tests use `pytest-asyncio`; HTTP mocking uses `respx`
- Add or update tests when modifying core logic. Run existing tests before concluding work.
- Do not remove tests or reduce coverage.

## Configuration

All settings in `src/reasoning_engine_pro/config.py` via `pydantic-settings`. See `.env.example` for all environment variables. Key ones: `LLM_PROVIDER` (vllm|openai), `REDIS_URL`, `WS_PORT` (default 8765), `MAX_CONCURRENT_CONNECTIONS` (default 50).

## Design Decisions

### Parent Repo Reference

This project reimplements `/Users/saketkr/Documents/opkey/codebases/ReasoningEngineBackend/` with the same behavior but cleaner architecture. Key improvement: OpenAI function calling replaces XML tag parsing (TokenProcessor). When porting features, replicate parent behavior exactly — same WebSocket event formats, same payload keys — but with better code.

### DD-1: Output Structure (Think Approach / Answer / Workflow JSON)

**Decision**: All three output types are structured tool calls, not XML tags parsed from streaming text.

| Parent (tag parsing) | Our approach (tool calls) | WebSocket event |
|---|---|---|
| `<THINK_APPROACH>` | `think_approach(summary)` tool | `think_approach` `{chat_id, content}` |
| `<ANSWER>` | `present_answer(content)` tool | `final_answer` `{chat_id, content}` |
| `<OPKEY_WORKFLOW_JSON>` | `submit_workflow(workflow_json, edges)` tool | `opkey_workflow_json` `{chat_id, workflow, job_name}` |
| Regular streaming | Regular streaming | `stream_response` `{chat_id, content, is_complete}` |

These tools are "output-only" — their executors just emit events, no external calls. WebSocket event payloads must match parent format exactly.

### DD-2: Multi-Model LLM Config

**Decision**: Separate config keys per agent. No global fallback — each agent has its own explicit config.

```
# Planner LLM (main reasoning model)
PLANNER_LLM_BASE_URL=http://...
PLANNER_LLM_API_KEY=...
PLANNER_LLM_MODEL_NAME=Qwen/Qwen3-235B-A22B-FP8

# Validator LLM (cheaper model for validation + referencing)
VALIDATOR_LLM_BASE_URL=http://...
VALIDATOR_LLM_API_KEY=...
VALIDATOR_LLM_MODEL_NAME=Qwen/Qwen2.5-72B-Instruct-AWQ
```

Existing `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME` keys are renamed to `PLANNER_LLM_*`. The `LLM_PROVIDER` key (vllm|openai) applies to both — they share the same provider type, just different endpoints/models. Each gets its own `ILLMProvider` instance created by the factory.

### DD-3: Validator Architecture — Pluggable Pipeline

**Decision**: Validation uses a pipeline of pluggable validators behind a common interface. Run sequentially — structural first, LLM second. Each validator is independently testable and can be added/removed without touching other code.

```
IWorkflowValidator (interface)
  ├── StructuralValidator — block IDs, edge refs, reachability (blocking, no LLM)
  ├── LLMBlockValidator — per-block task block correction, pillar/module, templates (blocking, uses validator LLM)
  └── EdgeConnectionValidator — disconnected block detection (non-blocking, warnings only)

ValidationPipeline — orchestrates validators in order, stops on blocking failure
ValidationContext — carries workflow, conversation_id, user_query, etc. through the pipeline
ValidationResult — accumulates errors, warnings, corrections across all validators
```

Each validator declares `is_blocking: bool`. If a blocking validator fails, the pipeline short-circuits. Non-blocking validators run regardless and contribute warnings. The pipeline is assembled in the DI container (`Dependencies`), making it easy to plug in/out validators via config or code.

### DD-4: Query Refinement — Three Pluggable Modes

**Decision**: Query refinement is a strategy behind `IQueryPreprocessor`. Three modes, selectable via config:

```
QUERY_REFINEMENT_MODE=separate|inline|disabled   (default: separate)
```

| Mode | Class | Behavior |
|------|-------|----------|
| `separate` | `QueryRefinementPreprocessor` | Separate LLM call before planner. Output becomes additional context. Matches parent repo. |
| `inline` | `InlineRefinementPreprocessor` | Refinement guidance folded into planner system prompt. No extra LLM call. |
| `disabled` | `PassthroughPreprocessor` | No-op. Planner gets raw user query. |

All implement `IQueryPreprocessor.preprocess(query, history, ...) -> PreprocessedQuery`. The orchestrator is agnostic to which mode is active. The `separate` mode uses the planner LLM provider (same reasoning model as parent). Factory in DI container selects implementation based on config.

### DD-5: Referencing Agent — Toggleable

**Decision**: Referencing agent runs after validation to populate mandatory workflow inputs. Toggleable via config, uses the validator LLM (cheaper model).

```
ENABLE_REFERENCING=true|false   (default: true)
```

When enabled, `ReferencingAgent` receives the validated workflow + user conversation history + task block definitions + environment data, and fills in unfilled mandatory inputs (StaticValue / ReferencedOutputVariableName). Uses its own prompt (ported from parent's `referencing_prompt.py`). When disabled, a passthrough returns the workflow unchanged. Separate class, not part of the validation pipeline — it modifies the workflow, not validates it.

### DD-6: Block Templates as Pydantic Models

**Decision**: Block templates are Pydantic models in `core/schemas/block_templates.py`. Captures all parent fields including `data_type` sub-structure (DataType, DataFormat, LovValues, fileTypesToSupport), KeywordId, group_name, sub_group, isEnabled.

Three predefined templates: `AI_BLOCK_TEMPLATE` (AskWilfred), `MANUAL_BLOCK_TEMPLATE` (HumanDependent), and `TASK_BLOCK_TEMPLATE` (generic, populated from API). The LLM validator uses these to enforce correct block structure — deep-copies template, injects LLM's values, ensures field correctness. Special handling for `CreateDiscoverySnapshot` (auto-populated dates, prerequisite for test generation workflows — must appear before test blocks). Discovery block processing lives in the LLM validator.

### DD-7: Prompt Organization — Hybrid (Templates + Domain Data)

**Decision**: Prompt text lives in `.md` template files with `{placeholders}`. Domain knowledge (pillar/module maps, config sequences, business process maps) lives as structured Python dicts in `domain_data.py`. Thin Python builder functions combine templates + domain data + runtime args.

```
agents/prompts/
├── templates/               # Pure prompt text with {placeholders}
│   ├── planner_system.md
│   ├── validation.md
│   ├── query_refinement.md
│   ├── referencing.md
│   ├── executor.md
│   └── misc/
│       ├── job_name.md
│       └── json_extraction.md
├── domain_data.py           # PILLAR_MODULE_MAP, BUSINESS_PROCESS_MAP, CONFIG_SEQUENCES (Python dicts)
├── planner.py               # get_planner_prompt(task_blocks, pillar_data, few_shot, user_info)
├── validation.py            # get_validation_prompt(block, search_results, workflow, edges, user_query)
├── query_refinement.py      # get_query_refinement_prompt(task_blocks)
├── referencing.py           # get_referencing_prompt(workflow, history, task_blocks, env_data)
└── loader.py                # PromptLoader — loads and caches .md templates, injects placeholders
```

Builder functions are the single source of truth for prompt assembly. No `.replace()` calls scattered in agent code.

### DD-8: Job Name Generation — LLM with Regex Fallback (deferred: Executor Agent — separate feature, not part of this phase)

**Decision**: Primary: LLM-based job name generation using the validator LLM (cheap model) with a prompt (ported from parent's `misc_prompts.py`). Produces natural 60-80 char names. Fallback: current regex-based generator if LLM fails or times out. `JobNameGenerator` tries LLM first, catches errors, falls back to regex.

### DD-9: Token-Based Message Summarization

**Decision**: Implement automatic LLM-based message summarization when conversation history approaches context limits. Matches parent repo behavior.

```
How it works:
1. Before each LLM call, estimate input token count (4 chars ≈ 1 token, no tiktoken)
2. If estimated tokens > configurable limit (default: 100,000), trigger summarization
3. Summarization uses validator LLM (cheap model) with a dedicated prompt
4. Summarized output replaces conversation history (system prompt preserved)
5. Re-estimate tokens after summarization and proceed

Summarization prompt rules (from parent):
- Preserve ALL user clarifications exactly as stated
- Remove duplicate/redundant content from web results and agent messages
- Trim agent reasoning to just what's necessary for context
- Structure summary by content type (User Clarification, Web Results, Agent Context)
```

```
TOKEN_SUMMARIZATION_LIMIT=100000       # Trigger threshold (estimated tokens)
```

Implementation lives in a `MessageSummarizer` class in `services/` or `agents/`. Called from the LLM provider layer (or orchestrator) before sending messages to the API. The summarizer is a service, not an agent — it's a utility that transforms message lists, not a reasoning loop.

### DD-10: Orchestrator Flow — Single Coordinator

**Decision**: Keep one `ConversationOrchestrator` class that calls each step sequentially. No sub-orchestrators. The updated flow:

```
User message arrives
  1. Query Refinement (IQueryPreprocessor — separate/inline/disabled via config)
  2. Planner LLM loop (tools: web_search, task_block_search, clarify,
                        think_approach, present_answer, submit_workflow)
  3. When submit_workflow tool is called:
     a. ValidationPipeline runs validators in order:
        - StructuralValidator (blocking)
        - LLMBlockValidator (blocking, uses validator LLM)
        - EdgeConnectionValidator (non-blocking, warnings)
     b. ReferencingAgent (if enabled) — populates mandatory inputs
     c. JobNameGenerator — LLM with regex fallback
     d. Emit opkey_workflow_json event to client
```

New steps (1, 3a-LLM, 3b) are injected via constructor dependencies. The orchestrator delegates, never owns logic.

### DD-11: Continuation Prompts — System Prompt Guidance Only

**Decision**: No per-result wrapper prompts. Instead, the planner system prompt includes a "Using Tool Results" section with guidance on how to interpret and use results from each tool (web_search, task_block_search, clarify). This is cleaner than the parent's approach (which wraps each tool result in a continuation prompt) because OpenAI function calling already provides structured tool results with context.

The guidance in the system prompt covers:
- **Web search**: Analyze relevance, discard irrelevant results, use for workflow design
- **Task block search**: Verify action_code matches, check block type correctness
- **Clarification**: Incorporate user answers, don't re-ask the same question

### DD-12: Langfuse Deep Integration

**Decision**: Every LLM call gets its own Langfuse generation/span within the conversation trace. Full token counts (input/output/total), latencies, model name, and tool call metadata.

Trace hierarchy:
```
Trace (conversation_id)
  ├── Span: query_refinement
  │   └── Generation: refiner LLM call
  ├── Span: planner_loop
  │   ├── Generation: planner LLM call (iteration 1)
  │   ├── Span: tool_execution (web_search)
  │   ├── Generation: planner LLM call (iteration 2)
  │   └── ...
  ├── Span: validation
  │   ├── Span: structural_validation
  │   ├── Generation: llm_block_validation (per block)
  │   └── Span: edge_validation
  ├── Span: referencing
  │   └── Generation: referencing LLM call
  ├── Span: summarization (if triggered)
  │   └── Generation: summarizer LLM call
  └── Span: job_name_generation
      └── Generation: job name LLM call
```

The `LangfuseTracer` class is expanded to support nested spans and generations. Each agent/service receives the tracer via dependency injection and creates its own spans. Token counts come from LLM response metadata (usage field).

### DD-13: Validation Failure → Planner Feedback Loop

**Decision**: When `submit_workflow` is called and the validation pipeline returns blocking errors, the errors are returned as the tool result for `submit_workflow`. The planner gets another iteration to fix the workflow and resubmit. This matches parent behavior.

The `submit_workflow` tool executor:
1. Receives workflow JSON from the planner
2. Runs ValidationPipeline
3. If blocking errors → returns error details as tool result (planner retries)
4. If no blocking errors → runs ReferencingAgent, JobNameGenerator, emits `opkey_workflow_json` event, returns success

Max retries is bounded by the planner loop's max iterations (currently 10). If the planner exhausts iterations without producing a valid workflow, the orchestrator emits an error event.

### DD-14: WebSocket Payload Schemas & User Context

**Decision**: Implement full user context from the actual WebSocket payloads. The `start_chat` payload includes `userDTO`, `domain`, `keycloak_token`, `project_key`, and other fields that flow into the referencing agent and prompts.

**`start_chat` payload schema:**
```json
{
  "event": "start_chat",
  "payload": {
    "chat_id": "uuid",
    "message": "user query text",
    "user_id": "uuid",
    "service_type": "planner",
    "attachment": [],
    "userDTO": {
      "U_ID": "uuid",
      "Name": "string",
      "UserName": "email",
      "email_ID": "email",
      "Is_Enabled": true,
      "CreatedOn": "datetime",
      "CreatedBy": "uuid",
      "LastModifiedOn": "datetime",
      "LastModifiedBy": "uuid",
      "Is_SuperAdmin": false,
      "Email_Verified_On": "datetime",
      "Last_Password_Change": "datetime",
      "isAutoCreated": false,
      "ForcePasswordChange": false,
      "ApiKey": "string",
      "Keycloak_SubjectId": "uuid",
      "UserImage": "nullable string",
      "idp_Groups": []
    },
    "domain": "https://instance.example.com",
    "history": "",
    "clarification_id": null,
    "keycloak_token": "string",
    "project_key": "string"
  }
}
```

Pydantic models: `StartChatPayload`, `UserDTO` in `core/schemas/messages.py`. The `userDTO`, `domain`, `keycloak_token`, and `project_key` are stored in conversation state and passed to the referencing agent and prompt builders. The `service_type` field is used to route between planner vs other services (future).

**`provide_clarification` payload:**
```json
{
  "event": "provide_clarification",
  "payload": {
    "chat_id": "uuid",
    "user_id": "uuid",
    "message_id": "uuid",
    "response": "string (user's answer to clarification questions)"
  }
}
```

### DD-15: WebSocket Event Schemas (Server → Client) — Must Match Parent Exactly

All outgoing events MUST match the parent repo's payload format exactly since the existing UI consumes them. Here is the complete schema reference:

**Connection Management:**
```
pong → { timestamp: float }
max_concurrent_connections_exceeded → { message: str, max_allowed_connections: str, timestamp: float }
```

**Session Lifecycle:**
```
processing_started → { chat_id: str, message_id: str }
chat_ended → { chat_id: str, message: str }
```

**Streaming:**
```
stream_response → { message_id: str, content: str, is_complete: bool, timestamp: float }
```

**Search Operations:**
```
web_search_started → { chat_id: str, message_id: str, search_id: str(uuid), queries: list[str] }
web_search_results → { chat_id: str, message_id: str, search_id: str, results: list[{query, content, sources}] }
task_block_search_started → { chat_id: str, message_id: str, search_id: str(uuid), queries: list[str] }
task_block_search_results → { chat_id: str, message_id: str, search_id: str, results: list[{query, blocks}], all_searched_actions: list[str] }
```

**Workflow Generation:**
```
think_approach → { chat_id: str, message_id: str, think_approach: str }
final_answer → { chat_id: str, message_id: str, answer_content: str, answer_json_content: str }
validator_progress_update → { chat_id: str, message_id: str, progress: int, totalNodes: int, block_name: str, timestamp: float }
opkey_workflow_json → { graph_data: list[dict], chat_id: str, message_id: str, opkey_workflow_id: str(uuid), json_data: list[dict], job_name: str }
```

**Clarification Flow:**
```
clarification_requested → { chat_id: str, message_id: str, clarification_id: str(uuid), questions: list[str] }
clarification_received → { chat_id: str, message_id: str, clarification_id: str }
clarification_processing → { message: str, chat_id: str, message_id: str, clarification_id: str }
```

**Referencing:**
```
referencing_started → { chat_id: str, message_id: str, message: str }
```

**Errors:**
```
error → { chat_id: str, message_id: str, message: str }
continuation_error → { chat_id: str, message_id: str, error: str, continuation_type: str }
```

### DD-16: Heartbeat Disconnection & Process Cancellation

**Decision**: Implement heartbeat-based connection health monitoring with active process cancellation on dead connections.

**Heartbeat disconnection logic:**
- Server sends periodic heartbeat/ping to each connected client (configurable interval)
- If a client fails to respond for N consecutive heartbeats (configurable threshold), the connection is considered dead
- On dead connection detection:
  1. Cancel any ongoing LLM inference for that `chat_id` (via asyncio task cancellation)
  2. Cancel any pending tool executions (search, clarification wait)
  3. Clean up connection from the connection manager
  4. Log the disconnection event
- Config: `HEARTBEAT_INTERVAL_SECONDS=30`, `HEARTBEAT_MAX_MISSED=3`

This requires the orchestrator/planner to use cancellable asyncio tasks, and a `CancellationToken` or similar mechanism passed through the processing chain so any step can check if it should abort.

### DD-17: Error Masking — No Raw Errors to Client

**Decision**: Never send raw exception messages or implementation details to the client. All errors emitted via WebSocket are mapped to user-friendly, sanitized messages. Full details are logged server-side only.

```
ErrorMapper (maps internal errors → client-safe messages):

  StorageError          → "A temporary storage issue occurred. Please try again."
  ToolExecutionError    → "Search service is temporarily unavailable." / "Unable to retrieve task blocks."
  LLM timeout/error     → "The AI service is temporarily unavailable. Please try again."
  Validation failure    → "We encountered an issue processing your workflow. Retrying..."
  Connection error      → "A connection issue occurred. Please check your network."
  Rate limit            → "Service is busy. Please wait a moment and try again."
  Unknown/unhandled     → "An unexpected error occurred. Please try again."
```

Implementation:
- `ErrorMapper` class in `core/errors.py` with a `to_client_message(exception) -> str` method
- Maps exception types to predefined safe messages
- Includes an error_code (e.g., `STORAGE_ERROR`, `LLM_UNAVAILABLE`) for programmatic client handling
- Full exception + traceback logged via structlog at ERROR level with `conversation_id` context
- The `error` WebSocket event payload becomes: `{ chat_id, message_id, message: str (safe), error_code: str }`

The `error_code` field is an addition to the parent schema — it doesn't break the UI (extra field ignored) but enables smarter client-side handling in the future.

## Safety Constraints

- Do not change public interfaces without confirmation.
- Do not modify container or deployment configuration unless requested.
- When unsure, ask clarifying questions. Do not guess intent. Stop before making irreversible or broad changes.
