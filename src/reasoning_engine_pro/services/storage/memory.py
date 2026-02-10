"""In-memory storage implementation for testing."""

from datetime import datetime, timedelta
from typing import Optional

from ...core.interfaces.storage import IConversationStorage
from ...core.schemas.messages import ChatMessage, ConversationState


class InMemoryStorage(IConversationStorage):
    """In-memory conversation storage for testing."""

    def __init__(self, default_ttl: int = 86400):
        self._history: dict[str, list[ChatMessage]] = {}
        self._state: dict[str, ConversationState] = {}
        self._drafts: dict[str, str] = {}
        self._expiry: dict[str, datetime] = {}
        self._default_ttl = default_ttl
        self._clarification_requests: dict[str, list[str]] = {}
        self._clarification_responses: dict[str, str] = {}
        self._events: dict[str, list[dict]] = {}

    def _is_expired(self, conversation_id: str) -> bool:
        """Check if conversation has expired."""
        if conversation_id not in self._expiry:
            return True
        return datetime.utcnow() > self._expiry[conversation_id]

    def _extend_expiry(self, conversation_id: str, ttl_seconds: int) -> None:
        """Extend conversation expiry."""
        self._expiry[conversation_id] = datetime.utcnow() + timedelta(
            seconds=ttl_seconds
        )

    async def save_message(self, conversation_id: str, message: ChatMessage) -> bool:
        """Save a message to conversation history."""
        if conversation_id not in self._history:
            self._history[conversation_id] = []

        self._history[conversation_id].append(message)
        self._extend_expiry(conversation_id, self._default_ttl)
        return True

    async def get_history(
        self, conversation_id: str, max_messages: Optional[int] = None
    ) -> list[ChatMessage]:
        """Get conversation history."""
        if self._is_expired(conversation_id):
            return []

        messages = self._history.get(conversation_id, [])
        if max_messages:
            messages = messages[-max_messages:]

        self._extend_expiry(conversation_id, self._default_ttl)
        return messages

    async def save_state(self, conversation_id: str, state: ConversationState) -> bool:
        """Save conversation state."""
        self._state[conversation_id] = state
        self._extend_expiry(conversation_id, self._default_ttl)
        return True

    async def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Get conversation state."""
        if self._is_expired(conversation_id):
            return None

        state = self._state.get(conversation_id)
        if state:
            self._extend_expiry(conversation_id, self._default_ttl)
        return state

    async def save_draft(self, conversation_id: str, draft: str) -> bool:
        """Save draft response."""
        self._drafts[conversation_id] = draft
        self._extend_expiry(conversation_id, self._default_ttl)
        return True

    async def get_draft(self, conversation_id: str) -> Optional[str]:
        """Get saved draft response."""
        if self._is_expired(conversation_id):
            return None
        return self._drafts.get(conversation_id)

    async def extend_ttl(self, conversation_id: str, ttl_seconds: int) -> bool:
        """Extend TTL for all conversation data."""
        self._extend_expiry(conversation_id, ttl_seconds)
        return True

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete all conversation data."""
        self._history.pop(conversation_id, None)
        self._state.pop(conversation_id, None)
        self._drafts.pop(conversation_id, None)
        self._expiry.pop(conversation_id, None)
        self._events.pop(conversation_id, None)

        # Clean up clarification data
        to_delete = [
            k
            for k in self._clarification_requests
            if k.startswith(f"{conversation_id}:")
        ]
        for key in to_delete:
            self._clarification_requests.pop(key, None)

        to_delete = [
            k
            for k in self._clarification_responses
            if k.startswith(f"{conversation_id}:")
        ]
        for key in to_delete:
            self._clarification_responses.pop(key, None)

        return True

    async def exists(self, conversation_id: str) -> bool:
        """Check if conversation exists."""
        if self._is_expired(conversation_id):
            return False
        return conversation_id in self._state

    # Clarification-specific methods
    async def save_clarification_request(
        self, conversation_id: str, clarification_id: str, questions: list[str]
    ) -> bool:
        """Save a clarification request."""
        key = f"{conversation_id}:{clarification_id}"
        self._clarification_requests[key] = questions
        return True

    async def save_clarification_response(
        self, conversation_id: str, clarification_id: str, response: str
    ) -> bool:
        """Save a clarification response."""
        key = f"{conversation_id}:{clarification_id}"
        self._clarification_responses[key] = response
        return True

    async def get_clarification_response(
        self, conversation_id: str, clarification_id: str
    ) -> Optional[str]:
        """Get a clarification response."""
        key = f"{conversation_id}:{clarification_id}"
        return self._clarification_responses.get(key)

    # Event methods
    async def add_event(
        self, conversation_id: str, event_type: str, payload: dict
    ) -> str:
        """Add event to in-memory stream."""
        if conversation_id not in self._events:
            self._events[conversation_id] = []

        event_id = f"{len(self._events[conversation_id])}"
        self._events[conversation_id].append(
            {"id": event_id, "type": event_type, "payload": payload}
        )
        return event_id

    async def get_events_since(
        self, conversation_id: str, last_id: str = "0"
    ) -> list[dict]:
        """Get events since given ID."""
        events = self._events.get(conversation_id, [])
        try:
            start_idx = int(last_id) + 1
        except ValueError:
            start_idx = 0
        return events[start_idx:]

    def clear(self) -> None:
        """Clear all data (for testing)."""
        self._history.clear()
        self._state.clear()
        self._drafts.clear()
        self._expiry.clear()
        self._clarification_requests.clear()
        self._clarification_responses.clear()
        self._events.clear()
