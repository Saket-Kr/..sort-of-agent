"""Tests for LLM providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reasoning_engine_pro.core.enums import MessageRole
from reasoning_engine_pro.core.schemas.messages import ChatMessage
from reasoning_engine_pro.llm.factory import LLMProviderFactory
from reasoning_engine_pro.llm.providers.openai import OpenAIProvider
from reasoning_engine_pro.llm.providers.vllm import VLLMProvider


class TestLLMProviderFactory:
    """Tests for LLMProviderFactory."""

    def test_create_vllm_provider(self):
        """Test creating VLLM provider."""
        provider = LLMProviderFactory.create(
            provider_type="vllm",
            base_url="http://localhost:8000/v1",
            api_key="test-key",
            model_name="test-model",
        )

        assert isinstance(provider, VLLMProvider)
        assert provider.model_name == "test-model"

    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        provider = LLMProviderFactory.create(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model_name="gpt-4",
        )

        assert isinstance(provider, OpenAIProvider)
        assert provider.model_name == "gpt-4"

    def test_create_unknown_provider(self):
        """Test creating unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider type"):
            LLMProviderFactory.create(
                provider_type="unknown",
                base_url="http://localhost:8000/v1",
                api_key="test-key",
                model_name="test-model",
            )


class TestVLLMProvider:
    """Tests for VLLMProvider."""

    @pytest.fixture
    def provider(self):
        """Create VLLM provider."""
        return VLLMProvider(
            base_url="http://localhost:8000/v1",
            api_key="test-key",
            model_name="test-model",
        )

    def test_model_name(self, provider):
        """Test model_name property."""
        assert provider.model_name == "test-model"

    def test_supports_function_calling(self, provider):
        """Test supports_function_calling property."""
        assert provider.supports_function_calling is True

    def test_messages_to_openai(self, provider):
        """Test message conversion."""
        messages = [
            ChatMessage(role=MessageRole.USER, content="Hello"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Hi there"),
        ]

        result = provider._messages_to_openai(messages)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Hi there"


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    @pytest.fixture
    def provider(self):
        """Create OpenAI provider."""
        return OpenAIProvider(
            api_key="test-key",
            model_name="gpt-4",
        )

    def test_model_name(self, provider):
        """Test model_name property."""
        assert provider.model_name == "gpt-4"

    def test_supports_function_calling(self, provider):
        """Test supports_function_calling property."""
        assert provider.supports_function_calling is True
