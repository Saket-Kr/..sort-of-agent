"""WebSocket event handlers."""

import traceback
from typing import Any, Optional

from fastapi import WebSocket

from ...agents.orchestrator import ConversationOrchestrator
from ...core.enums import EventType
from ...core.exceptions import ConversationNotFoundError, ReasoningEngineError
from ...core.schemas.messages import UserInfo
from ...observability.logger import get_logger
from ..dependencies import Dependencies
from .connection import ConnectionManager, WebSocketEventEmitter

logger = get_logger(__name__)


class WebSocketHandler:
    """Handles WebSocket events."""

    def __init__(
        self,
        dependencies: Dependencies,
        connection_manager: ConnectionManager,
    ):
        """
        Initialize handler.

        Args:
            dependencies: Application dependencies
            connection_manager: Connection manager
        """
        self._deps = dependencies
        self._manager = connection_manager

    async def handle_start_chat(
        self,
        websocket: WebSocket,
        payload: dict[str, Any],
    ) -> None:
        """
        Handle start_chat event.

        Args:
            websocket: Client WebSocket
            payload: Event payload containing chat_id, message, etc.
        """
        chat_id = payload.get("chat_id")
        message = payload.get("message", "")

        # Support both user_info and userDTO for backwards compatibility
        user_data = payload.get("userDTO") or {}

        # Support both attachments and attachment
        attachments = payload.get("attachment") or []

        # Extract additional context from payload
        user_id = payload.get("user_id")
        service_type = payload.get("service_type")
        domain = payload.get("domain")
        history = payload.get("history")
        project_key = payload.get("project_key")

        logger.info(
            "Received start_chat",
            chat_id=chat_id,
            message_preview=message[:100] if message else None,
            user_id=user_id,
            service_type=service_type,
        )

        if not chat_id:
            logger.warning("Missing chat_id in start_chat payload")
            await self._send_error(websocket, None, "INVALID_PAYLOAD", "Missing chat_id")
            return

        if not message:
            logger.warning("Missing message in start_chat payload", chat_id=chat_id)
            await self._send_error(
                websocket, chat_id, "INVALID_PAYLOAD", "Missing message"
            )
            return

        logger.info("Processing chat", chat_id=chat_id, message_length=len(message))

        try:
            # Create event emitter
            event_emitter = self._manager.get_event_emitter(websocket, chat_id)

            # Get orchestrator with event emitter
            orchestrator = await self._deps.get_orchestrator(event_emitter)

            # Parse user info
            user_info = UserInfo(**user_data) if user_data else None

            # Start conversation
            await orchestrator.start_conversation(
                conversation_id=chat_id,
                initial_message=message,
                user_info=user_info,
                attachments=attachments,
            )

        except Exception as e:
            logger.error(
                "Error in start_chat",
                chat_id=chat_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            await self._send_error(websocket, chat_id, "PROCESSING_ERROR", str(e))

    async def handle_provide_clarification(
        self,
        websocket: WebSocket,
        payload: dict[str, Any],
    ) -> None:
        """
        Handle provide_clarification event.

        Args:
            websocket: Client WebSocket
            payload: Event payload containing chat_id, clarification_id, response
        """
        chat_id = payload.get("chat_id")
        clarification_id = payload.get("clarification_id")
        response = payload.get("response", "")

        if not chat_id or not clarification_id:
            await self._send_error(
                websocket, chat_id, "INVALID_PAYLOAD", "Missing required fields"
            )
            return

        logger.info(
            "Handling clarification response",
            chat_id=chat_id,
            clarification_id=clarification_id,
        )

        try:
            # Create event emitter
            event_emitter = self._manager.get_event_emitter(websocket, chat_id)

            # Get orchestrator
            orchestrator = await self._deps.get_orchestrator(event_emitter)

            # Handle clarification
            await orchestrator.handle_clarification_response(
                conversation_id=chat_id,
                clarification_id=clarification_id,
                response=response,
            )

        except ConversationNotFoundError:
            await self._send_error(
                websocket, chat_id, "CONVERSATION_NOT_FOUND", "Conversation not found"
            )
        except ReasoningEngineError as e:
            await self._send_error(websocket, chat_id, "CLARIFICATION_ERROR", str(e))
        except Exception as e:
            logger.error(
                "Error handling clarification",
                chat_id=chat_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
            )
            await self._send_error(websocket, chat_id, "PROCESSING_ERROR", str(e))

    async def handle_end_chat(
        self,
        websocket: WebSocket,
        payload: dict[str, Any],
    ) -> None:
        """
        Handle end_chat event.

        Args:
            websocket: Client WebSocket
            payload: Event payload containing chat_id
        """
        chat_id = payload.get("chat_id")

        if not chat_id:
            return

        logger.info("Ending chat", chat_id=chat_id)

        try:
            orchestrator = await self._deps.get_orchestrator()
            await orchestrator.end_conversation(chat_id)
        except Exception as e:
            logger.error("Error ending chat", chat_id=chat_id, error=str(e))

    async def handle_ping(self, websocket: WebSocket) -> None:
        """Handle ping event."""
        await websocket.send_json({"event": "pong", "payload": {}})

    async def handle_input_analysis(
        self,
        websocket: WebSocket,
        payload: dict[str, Any],
    ) -> None:
        """
        Handle input_analysis event.

        Args:
            websocket: Client WebSocket
            payload: Event payload containing chat_id, message
        """
        chat_id = payload.get("chat_id")
        message = payload.get("message", "")

        if not chat_id or not message:
            await self._send_error(
                websocket, chat_id, "INVALID_PAYLOAD", "Missing required fields"
            )
            return

        # TODO: Implement input analysis logic
        # This would analyze the user's input for references, entities, etc.
        analysis = {
            "chat_id": chat_id,
            "message": message,
            "analysis": {
                "entities": [],
                "references": [],
                "intent": "workflow_creation",
            },
        }

        await websocket.send_json({
            "event": "input_analysis_result",
            "payload": analysis,
        })

    async def _send_error(
        self,
        websocket: WebSocket,
        chat_id: Optional[str],
        error_code: str,
        message: str,
    ) -> None:
        """Send error event."""
        await websocket.send_json({
            "event": EventType.ERROR.value,
            "payload": {
                "chat_id": chat_id,
                "error_code": error_code,
                "message": message,
            },
        })
