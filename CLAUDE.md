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

## Safety Constraints

- Do not change public interfaces without confirmation.
- Do not modify container or deployment configuration unless requested.
- When unsure, ask clarifying questions. Do not guess intent. Stop before making irreversible or broad changes.
