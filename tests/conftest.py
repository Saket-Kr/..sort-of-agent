"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from reasoning_engine_pro.api.app import create_app
from reasoning_engine_pro.config import Settings
from reasoning_engine_pro.core.enums import MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage
from reasoning_engine_pro.core.schemas.workflow import Workflow
from reasoning_engine_pro.services.storage.memory import InMemoryStorage
from tests.fixtures.sample_workflows import SampleWorkflows


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        llm_provider="vllm",
        llm_base_url="http://localhost:8000/v1",
        llm_api_key="test-key",
        llm_model_name="test-model",
        redis_url="",  # Use in-memory storage
        max_concurrent_connections=10,
    )


@pytest.fixture
def memory_storage() -> InMemoryStorage:
    """Create in-memory storage for testing."""
    return InMemoryStorage()


@pytest.fixture
def sample_workflow() -> Workflow:
    """Create a sample workflow for testing."""
    return SampleWorkflows.simple_export()


@pytest.fixture
def sample_messages() -> list[ChatMessage]:
    """Create sample chat messages."""
    return [
        ChatMessage(
            role=MessageRole.USER,
            content="Create a workflow to export HCM configuration",
        ),
    ]


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.model_name = "test-model"
    provider.supports_function_calling = True

    async def mock_generate_stream(*args, **kwargs):
        # Yield a simple response
        from reasoning_engine_pro.core.interfaces.llm_provider import LLMStreamChunk

        yield LLMStreamChunk(content="Test response", is_complete=True)

    provider.generate_stream = mock_generate_stream

    async def mock_generate(*args, **kwargs):
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content="Test response",
        )

    provider.generate = mock_generate

    return provider


@pytest.fixture
def test_client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Create test client for API testing."""
    from reasoning_engine_pro.api.dependencies import Dependencies

    # Reset singleton
    Dependencies.reset()

    app = create_app(test_settings)
    with TestClient(app) as client:
        yield client

    # Cleanup
    Dependencies.reset()


@pytest.fixture
async def async_memory_storage() -> AsyncGenerator[InMemoryStorage, None]:
    """Create async in-memory storage."""
    storage = InMemoryStorage()
    yield storage
    storage.clear()
