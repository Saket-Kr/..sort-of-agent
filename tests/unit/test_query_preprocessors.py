"""Tests for query preprocessor implementations and factory."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from reasoning_engine_pro.agents.preprocessors.factory import QueryPreprocessorFactory
from reasoning_engine_pro.agents.preprocessors.inline_refinement import (
    InlineRefinementPreprocessor,
)
from reasoning_engine_pro.agents.preprocessors.passthrough import PassthroughPreprocessor
from reasoning_engine_pro.agents.preprocessors.query_refinement import (
    QueryRefinementPreprocessor,
)
from reasoning_engine_pro.config import Settings
from reasoning_engine_pro.core.enums import MessageRole
from reasoning_engine_pro.core.interfaces.query_preprocessor import IQueryPreprocessor
from reasoning_engine_pro.core.schemas.messages import ChatMessage


class TestPassthroughPreprocessor:
    @pytest.fixture
    def preprocessor(self):
        return PassthroughPreprocessor()

    def test_implements_interface(self, preprocessor):
        assert isinstance(preprocessor, IQueryPreprocessor)

    @pytest.mark.asyncio
    async def test_returns_message_unchanged(self, preprocessor):
        result = await preprocessor.preprocess("Export HCM config", [])
        assert result == "Export HCM config"

    @pytest.mark.asyncio
    async def test_ignores_history_and_user_info(self, preprocessor):
        history = [ChatMessage(role=MessageRole.USER, content="prev")]
        result = await preprocessor.preprocess("msg", history)
        assert result == "msg"


class TestQueryRefinementPreprocessor:
    @pytest.fixture
    def mock_llm(self, mock_llm_provider):
        return mock_llm_provider

    @pytest.fixture
    def preprocessor(self, mock_llm):
        return QueryRefinementPreprocessor(llm_provider=mock_llm)

    def test_implements_interface(self, preprocessor):
        assert isinstance(preprocessor, IQueryPreprocessor)

    @pytest.mark.asyncio
    async def test_calls_llm_and_returns_refined(self, preprocessor, mock_llm):
        async def _generate(messages, **kwargs):
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content="Refined: Start by searching for export blocks",
            )

        mock_llm.generate = _generate

        result = await preprocessor.preprocess("Export config", [])
        assert "Refined" in result
        assert "export blocks" in result

    @pytest.mark.asyncio
    async def test_falls_back_on_llm_failure(self, preprocessor, mock_llm):
        async def _generate(messages, **kwargs):
            raise RuntimeError("LLM unavailable")

        mock_llm.generate = _generate

        result = await preprocessor.preprocess("Export config", [])
        assert result == "Export config"

    @pytest.mark.asyncio
    async def test_emits_events(self, mock_llm):
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        preprocessor = QueryRefinementPreprocessor(
            llm_provider=mock_llm, event_emitter=emitter
        )

        result = await preprocessor.preprocess("test query", [])
        assert emitter.emit.call_count >= 2  # started + completed


class TestInlineRefinementPreprocessor:
    @pytest.fixture
    def preprocessor(self):
        return InlineRefinementPreprocessor()

    def test_implements_interface(self, preprocessor):
        assert isinstance(preprocessor, IQueryPreprocessor)

    @pytest.mark.asyncio
    async def test_appends_guidance(self, preprocessor):
        result = await preprocessor.preprocess("Export HCM config", [])
        assert result.startswith("Export HCM config")
        assert "Query Refinement" in result
        assert "task_block_search" in result

    @pytest.mark.asyncio
    async def test_includes_config_sequences(self, preprocessor):
        result = await preprocessor.preprocess("test", [])
        assert "Core HR" in result or "General Ledger" in result

    @pytest.mark.asyncio
    async def test_includes_pillar_module_data(self, preprocessor):
        result = await preprocessor.preprocess("test", [])
        assert "HCM" in result or "Financials" in result


class TestQueryPreprocessorFactory:
    def test_disabled_returns_passthrough(self, test_settings):
        preprocessor = QueryPreprocessorFactory.create(test_settings)
        assert isinstance(preprocessor, PassthroughPreprocessor)

    def test_separate_requires_llm(self, test_settings):
        test_settings.query_refinement_mode = "separate"
        with pytest.raises(ValueError, match="requires an LLM provider"):
            QueryPreprocessorFactory.create(test_settings)

    def test_separate_with_llm(self, test_settings, mock_llm_provider):
        test_settings.query_refinement_mode = "separate"
        preprocessor = QueryPreprocessorFactory.create(
            test_settings, llm_provider=mock_llm_provider
        )
        assert isinstance(preprocessor, QueryRefinementPreprocessor)

    def test_inline_returns_inline(self, test_settings):
        test_settings.query_refinement_mode = "inline"
        preprocessor = QueryPreprocessorFactory.create(test_settings)
        assert isinstance(preprocessor, InlineRefinementPreprocessor)

    def test_unknown_mode_returns_passthrough(self, test_settings):
        test_settings.query_refinement_mode = "disabled"
        preprocessor = QueryPreprocessorFactory.create(test_settings)
        assert isinstance(preprocessor, PassthroughPreprocessor)
