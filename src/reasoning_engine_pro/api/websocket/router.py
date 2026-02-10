"""WebSocket router."""

import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...core.enums import EventType
from ...core.exceptions import MaxConnectionsExceededError
from ...observability.logger import get_logger
from ..dependencies import Dependencies
from .connection import ConnectionManager
from .handlers import WebSocketHandler

logger = get_logger(__name__)

router = APIRouter()

# Global connection manager (initialized in app startup)
_connection_manager: ConnectionManager | None = None
_handler: WebSocketHandler | None = None


def init_websocket(dependencies: Dependencies, max_connections: int = 50) -> None:
    """Initialize WebSocket components."""
    global _connection_manager, _handler
    _connection_manager = ConnectionManager(max_connections=max_connections)
    _handler = WebSocketHandler(dependencies, _connection_manager)


def get_connection_manager() -> ConnectionManager:
    """Get the connection manager."""
    if _connection_manager is None:
        raise RuntimeError("WebSocket not initialized")
    return _connection_manager


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket endpoint."""
    if _connection_manager is None or _handler is None:
        await websocket.close(code=1011, reason="Server not initialized")
        return

    # Check connection limit
    if not await _connection_manager.can_connect():
        await websocket.accept()
        await websocket.send_json(
            {
                "event": EventType.MAX_CONCURRENT_CONNECTIONS_EXCEEDED.value,
                "payload": {
                    "message": "Maximum concurrent connections exceeded",
                    "max_connections": _connection_manager.max_connections,
                },
            }
        )
        await websocket.close(code=4000)
        return

    connection_id = await _connection_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")
            payload = data.get("payload", {})

            logger.info(
                "Received event", event_type=event_type, connection_id=connection_id
            )
            await _handler.dispatch(event_type, payload, websocket)

    except WebSocketDisconnect:
        logger.info("Client disconnected", connection_id=connection_id)
    except Exception as e:
        logger.error(
            "WebSocket error",
            connection_id=connection_id,
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )
    finally:
        await _connection_manager.disconnect(connection_id)
