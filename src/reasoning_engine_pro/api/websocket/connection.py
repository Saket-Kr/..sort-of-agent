"""WebSocket connection manager."""

import asyncio
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import WebSocket

from ...core.enums import EventType
from ...core.interfaces.event_emitter import IEventEmitter
from ...observability.logger import get_logger

logger = get_logger(__name__)


class WebSocketEventEmitter(IEventEmitter):
    """Event emitter that sends events over WebSocket.

    Payload formats are aligned with the parent repo's WebSocket protocol
    so the existing frontend can consume them without changes.
    """

    def __init__(
        self,
        websocket: WebSocket,
        conversation_id: str,
        message_id: Optional[str] = None,
    ):
        self._websocket = websocket
        self._conversation_id = conversation_id
        self._message_id = message_id

    def set_message_id(self, message_id: str) -> None:
        """Set the message_id for subsequent events."""
        self._message_id = message_id

    def _resolve_message_id(self, message_id: Optional[str]) -> Optional[str]:
        """Use explicit message_id if provided, otherwise fall back to instance default."""
        return message_id or self._message_id

    async def emit(self, event_type: EventType, payload: dict[str, Any]) -> None:
        """Emit an event over WebSocket."""
        try:
            await self._websocket.send_json(
                {
                    "event": event_type.value,
                    "payload": payload,
                }
            )
        except Exception as e:
            logger.error("Failed to emit event", event=event_type.value, error=str(e))

    async def emit_stream_chunk(
        self,
        conversation_id: str,
        chunk: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit a streaming response chunk."""
        await self.emit(
            EventType.STREAM_RESPONSE,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "content": chunk,
                "is_complete": False,
                "timestamp": datetime.now(tz=UTC).isoformat(),
            },
        )

    async def emit_error(
        self,
        conversation_id: str | None,
        error_code: str,
        message: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit an error event."""
        await self.emit(
            EventType.ERROR,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "error_code": error_code,
                "message": message,
            },
        )

    async def emit_clarification_request(
        self,
        conversation_id: str,
        clarification_id: str,
        questions: list[str],
        message_id: Optional[str] = None,
    ) -> None:
        """Emit a clarification request event."""
        await self.emit(
            EventType.CLARIFICATION_REQUESTED,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "clarification_id": clarification_id,
                "questions": questions,
            },
        )

    async def emit_tool_started(
        self,
        conversation_id: str,
        tool_name: str,
        event_type: EventType,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit a tool execution started event."""
        await self.emit(
            event_type,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "tool_name": tool_name,
            },
        )

    async def emit_tool_results(
        self,
        conversation_id: str,
        event_type: EventType,
        results: list[dict[str, Any]],
        query_count: int,
        total_results: int,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit tool results event."""
        await self.emit(
            event_type,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "results": results,
                "query_count": query_count,
                "total_results": total_results,
            },
        )

    async def emit_workflow(
        self,
        conversation_id: str,
        workflow: dict[str, Any],
        job_name: str | None = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit workflow output event."""
        await self.emit(
            EventType.OPKEY_WORKFLOW_JSON,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "graph_data": workflow,
                "json_data": workflow,
                "job_name": job_name,
            },
        )

    async def emit_validation_progress(
        self,
        conversation_id: str,
        stage: str,
        progress: float,
        message: str,
        errors: list[str] | None = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit validation progress update."""
        await self.emit(
            EventType.VALIDATOR_PROGRESS_UPDATE,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "stage": stage,
                "progress": progress,
                "message": message,
                "errors": errors or [],
            },
        )

    async def emit_think_approach(
        self,
        conversation_id: str,
        content: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit think_approach event."""
        await self.emit(
            EventType.THINK_APPROACH,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "think_approach": content,
            },
        )

    async def emit_final_answer(
        self,
        conversation_id: str,
        content: str,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit final_answer event."""
        await self.emit(
            EventType.FINAL_ANSWER,
            {
                "chat_id": conversation_id,
                "message_id": self._resolve_message_id(message_id),
                "answer_content": content,
                "answer_json_content": "",
            },
        )

    async def emit_chat_ended(
        self,
        conversation_id: str,
    ) -> None:
        """Emit chat_ended event."""
        await self.emit(
            EventType.CHAT_ENDED,
            {
                "chat_id": conversation_id,
            },
        )


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self, max_connections: int = 50):
        """
        Initialize connection manager.

        Args:
            max_connections: Maximum concurrent connections allowed
        """
        self._max_connections = max_connections
        self._active_connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        """Get number of active connections."""
        return len(self._active_connections)

    @property
    def max_connections(self) -> int:
        """Get maximum connections allowed."""
        return self._max_connections

    async def can_connect(self) -> bool:
        """Check if new connection is allowed."""
        async with self._lock:
            return self.active_count < self._max_connections

    async def connect(
        self, websocket: WebSocket, connection_id: Optional[str] = None
    ) -> str:
        """
        Accept and register a WebSocket connection.

        Args:
            websocket: WebSocket to connect
            connection_id: Optional custom connection ID

        Returns:
            Connection ID
        """
        await websocket.accept()

        async with self._lock:
            if connection_id is None:
                import uuid

                connection_id = str(uuid.uuid4())

            self._active_connections[connection_id] = websocket
            logger.info(
                "WebSocket connected",
                connection_id=connection_id,
                active_count=self.active_count,
            )

        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """
        Disconnect and unregister a WebSocket connection.

        Args:
            connection_id: Connection to disconnect
        """
        async with self._lock:
            if connection_id in self._active_connections:
                del self._active_connections[connection_id]
                logger.info(
                    "WebSocket disconnected",
                    connection_id=connection_id,
                    active_count=self.active_count,
                )

    def get_connection(self, connection_id: str) -> Optional[WebSocket]:
        """Get WebSocket by connection ID."""
        return self._active_connections.get(connection_id)

    async def send_to(
        self, connection_id: str, event: str, payload: dict[str, Any]
    ) -> bool:
        """
        Send message to specific connection.

        Args:
            connection_id: Target connection
            event: Event type
            payload: Event payload

        Returns:
            True if sent successfully
        """
        websocket = self._active_connections.get(connection_id)
        if websocket is None:
            return False

        try:
            await websocket.send_json({"event": event, "payload": payload})
            return True
        except Exception as e:
            logger.error(
                "Failed to send to connection",
                connection_id=connection_id,
                error=str(e),
            )
            return False

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        """
        Broadcast message to all connections.

        Args:
            event: Event type
            payload: Event payload
        """
        disconnected = []

        for conn_id, websocket in self._active_connections.items():
            try:
                await websocket.send_json({"event": event, "payload": payload})
            except Exception:
                disconnected.append(conn_id)

        # Clean up disconnected
        for conn_id in disconnected:
            await self.disconnect(conn_id)

    def get_event_emitter(
        self, websocket: WebSocket, conversation_id: str
    ) -> WebSocketEventEmitter:
        """Create event emitter for a WebSocket connection."""
        return WebSocketEventEmitter(websocket, conversation_id)
