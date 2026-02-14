"""Tests for error mapper."""

import pytest

from reasoning_engine_pro.core.error_mapper import ErrorMapper
from reasoning_engine_pro.core.exceptions import (
    ClarificationRequiredError,
    ConversationNotFoundError,
    LLMProviderError,
    MaxConnectionsExceededError,
    StorageError,
    ToolExecutionError,
    ValidationError,
    WorkflowParseError,
)


class TestErrorMapper:
    """Tests for ErrorMapper.to_client_error()."""

    @pytest.mark.parametrize(
        "exc, expected_code",
        [
            (LLMProviderError("model crashed"), "LLM_UNAVAILABLE"),
            (ToolExecutionError("timeout", "web_search"), "TOOL_ERROR"),
            (StorageError("redis down"), "STORAGE_ERROR"),
            (ValidationError("bad block"), "VALIDATION_ERROR"),
            (WorkflowParseError("invalid json"), "PARSE_ERROR"),
            (ConversationNotFoundError("abc-123"), "NOT_FOUND"),
            (ClarificationRequiredError("c1", ["q1"]), "CLARIFICATION_REQUIRED"),
            (MaxConnectionsExceededError(50), "MAX_CONNECTIONS"),
        ],
    )
    def test_maps_known_exceptions(self, exc: Exception, expected_code: str):
        code, message = ErrorMapper.to_client_error(exc)
        assert code == expected_code
        assert isinstance(message, str)
        assert len(message) > 0

    def test_unknown_exception_returns_internal_error(self):
        code, message = ErrorMapper.to_client_error(RuntimeError("something broke"))
        assert code == "INTERNAL_ERROR"
        assert "unexpected error" in message.lower()

    def test_never_leaks_raw_message(self):
        secret = "redis://admin:s3cret@internal-host:6379/0"
        exc = StorageError(secret)
        _, message = ErrorMapper.to_client_error(exc)
        assert secret not in message
        assert "s3cret" not in message
        assert "internal-host" not in message

    def test_never_leaks_tool_details(self):
        exc = ToolExecutionError(
            "Connection refused to http://10.0.0.5:9200",
            "task_block_search",
            {"query": "export config"},
        )
        _, message = ErrorMapper.to_client_error(exc)
        assert "10.0.0.5" not in message
        assert "Connection refused" not in message

    def test_subclass_matches_parent(self):
        """Subclasses of mapped exceptions should still match."""

        class CustomStorageError(StorageError):
            pass

        code, _ = ErrorMapper.to_client_error(CustomStorageError("custom"))
        assert code == "STORAGE_ERROR"
