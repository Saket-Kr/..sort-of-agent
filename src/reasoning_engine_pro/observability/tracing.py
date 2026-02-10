"""Langfuse tracing integration."""

from contextlib import contextmanager
from typing import Any, Generator, Optional

from langfuse import Langfuse


class LangfuseTracer:
    """Langfuse tracing wrapper."""

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str = "https://cloud.langfuse.com",
        enabled: bool = True,
    ):
        """
        Initialize Langfuse tracer.

        Args:
            public_key: Langfuse public key
            secret_key: Langfuse secret key
            host: Langfuse host URL
            enabled: Whether tracing is enabled
        """
        self._enabled = enabled and public_key and secret_key

        if self._enabled:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
        else:
            self._client = None

    @contextmanager
    def trace(
        self,
        name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Generator[Optional[Any], None, None]:
        """
        Create a trace context.

        Args:
            name: Trace name
            user_id: Optional user identifier
            session_id: Optional session identifier
            metadata: Optional metadata

        Yields:
            Trace object or None if disabled
        """
        if not self._enabled or not self._client:
            yield None
            return

        trace = self._client.trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        try:
            yield trace
        finally:
            pass  # Langfuse handles cleanup

    def span(
        self,
        trace: Any,
        name: str,
        input_data: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Any]:
        """
        Create a span within a trace.

        Args:
            trace: Parent trace
            name: Span name
            input_data: Optional input data
            metadata: Optional metadata

        Returns:
            Span object or None
        """
        if not self._enabled or trace is None:
            return None

        return trace.span(
            name=name,
            input=input_data,
            metadata=metadata or {},
        )

    def generation(
        self,
        trace: Any,
        name: str,
        model: str,
        input_data: Optional[dict] = None,
        output: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Any]:
        """
        Log an LLM generation.

        Args:
            trace: Parent trace
            name: Generation name
            model: Model name
            input_data: Input messages/prompt
            output: Generated output
            metadata: Optional metadata

        Returns:
            Generation object or None
        """
        if not self._enabled or trace is None:
            return None

        return trace.generation(
            name=name,
            model=model,
            input=input_data,
            output=output,
            metadata=metadata or {},
        )

    def flush(self) -> None:
        """Flush pending traces."""
        if self._client:
            self._client.flush()

    def shutdown(self) -> None:
        """Shutdown tracer."""
        if self._client:
            self._client.flush()
            self._client.shutdown()
