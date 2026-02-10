"""Integration tests for WebSocket API."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from reasoning_engine_pro.api.app import create_app


class TestWebSocketEndpoint:
    """Integration tests for WebSocket endpoint."""

    @pytest.fixture
    def client(self, test_settings):
        """Create test client."""
        from reasoning_engine_pro.api.dependencies import Dependencies

        Dependencies.reset()

        app = create_app(test_settings)
        with TestClient(app) as client:
            yield client

        Dependencies.reset()

    def test_websocket_connect(self, client):
        """Test WebSocket connection."""
        with client.websocket_connect("/ws") as websocket:
            # Connection should succeed
            assert websocket is not None

    def test_websocket_ping_pong(self, client):
        """Test ping/pong heartbeat."""
        with client.websocket_connect("/ws") as websocket:
            # Send ping
            websocket.send_json({"event": "ping", "payload": {}})

            # Receive pong
            response = websocket.receive_json()
            assert response["event"] == "pong"

    def test_websocket_unknown_event(self, client):
        """Test unknown event handling."""
        with client.websocket_connect("/ws") as websocket:
            # Send unknown event
            websocket.send_json({"event": "unknown_event", "payload": {}})

            # Should receive error
            response = websocket.receive_json()
            assert response["event"] == "error"
            assert "UNKNOWN_EVENT" in response["payload"]["error_code"]

    def test_websocket_start_chat_missing_chat_id(self, client):
        """Test start_chat without chat_id."""
        with client.websocket_connect("/ws") as websocket:
            # Send start_chat without chat_id
            websocket.send_json(
                {
                    "event": "start_chat",
                    "payload": {"message": "Hello"},
                }
            )

            # Should receive error
            response = websocket.receive_json()
            assert response["event"] == "error"
            assert "chat_id" in response["payload"]["message"].lower()

    def test_websocket_start_chat_missing_message(self, client):
        """Test start_chat without message."""
        with client.websocket_connect("/ws") as websocket:
            # Send start_chat without message
            websocket.send_json(
                {
                    "event": "start_chat",
                    "payload": {"chat_id": "test-123"},
                }
            )

            # Should receive error
            response = websocket.receive_json()
            assert response["event"] == "error"
            assert "message" in response["payload"]["message"].lower()
