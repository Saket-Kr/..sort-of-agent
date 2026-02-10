"""Redis storage implementation."""

import json
from typing import Optional

import redis.asyncio as redis

from ...core.exceptions import StorageError
from ...core.interfaces.storage import IConversationStorage
from ...core.schemas.messages import ChatMessage, ConversationState


class RedisStorage(IConversationStorage):
    """Redis-based conversation storage with TTL support."""

    # Key patterns
    HISTORY_KEY = "conv:{id}:history"
    STATE_KEY = "conv:{id}:state"
    DRAFT_KEY = "conv:{id}:draft"
    CLARIFY_REQUEST_KEY = "clarify:{conv_id}:{clarify_id}:request"
    CLARIFY_RESPONSE_KEY = "clarify:{conv_id}:{clarify_id}:response"
    EVENTS_KEY = "events:{id}"

    def __init__(self, redis_url: str, default_ttl: int = 86400):
        """
        Initialize Redis storage.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds (default: 24 hours)
        """
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is None:
            self._client = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None

    def _get_client(self) -> redis.Redis:
        """Get Redis client, raising if not connected."""
        if self._client is None:
            raise StorageError("Redis client not connected. Call connect() first.")
        return self._client

    async def save_message(self, conversation_id: str, message: ChatMessage) -> bool:
        """Save a message to conversation history."""
        try:
            client = self._get_client()
            key = self.HISTORY_KEY.format(id=conversation_id)

            # Serialize message
            message_json = message.model_dump_json()

            # Append to list and set TTL
            async with client.pipeline() as pipe:
                await pipe.rpush(key, message_json)
                await pipe.expire(key, self._default_ttl)
                await pipe.execute()

            return True
        except Exception as e:
            raise StorageError(f"Failed to save message: {e}")

    async def get_history(
        self, conversation_id: str, max_messages: Optional[int] = None
    ) -> list[ChatMessage]:
        """Get conversation history."""
        try:
            client = self._get_client()
            key = self.HISTORY_KEY.format(id=conversation_id)

            # Get all messages (or limited)
            if max_messages:
                messages_json = await client.lrange(key, -max_messages, -1)
            else:
                messages_json = await client.lrange(key, 0, -1)

            # Deserialize messages
            messages = []
            for msg_json in messages_json:
                messages.append(ChatMessage.model_validate_json(msg_json))

            # Extend TTL on access
            await client.expire(key, self._default_ttl)

            return messages
        except Exception as e:
            raise StorageError(f"Failed to get history: {e}")

    async def save_state(self, conversation_id: str, state: ConversationState) -> bool:
        """Save conversation state."""
        try:
            client = self._get_client()
            key = self.STATE_KEY.format(id=conversation_id)

            state_json = state.model_dump_json()
            await client.set(key, state_json, ex=self._default_ttl)

            return True
        except Exception as e:
            raise StorageError(f"Failed to save state: {e}")

    async def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Get conversation state."""
        try:
            client = self._get_client()
            key = self.STATE_KEY.format(id=conversation_id)

            state_json = await client.get(key)
            if state_json is None:
                return None

            # Extend TTL on access
            await client.expire(key, self._default_ttl)

            return ConversationState.model_validate_json(state_json)
        except Exception as e:
            raise StorageError(f"Failed to get state: {e}")

    async def save_draft(self, conversation_id: str, draft: str) -> bool:
        """Save draft response."""
        try:
            client = self._get_client()
            key = self.DRAFT_KEY.format(id=conversation_id)

            await client.set(key, draft, ex=self._default_ttl)
            return True
        except Exception as e:
            raise StorageError(f"Failed to save draft: {e}")

    async def get_draft(self, conversation_id: str) -> Optional[str]:
        """Get saved draft response."""
        try:
            client = self._get_client()
            key = self.DRAFT_KEY.format(id=conversation_id)

            draft = await client.get(key)
            return draft
        except Exception as e:
            raise StorageError(f"Failed to get draft: {e}")

    async def extend_ttl(self, conversation_id: str, ttl_seconds: int) -> bool:
        """Extend TTL for all conversation data."""
        try:
            client = self._get_client()

            keys = [
                self.HISTORY_KEY.format(id=conversation_id),
                self.STATE_KEY.format(id=conversation_id),
                self.DRAFT_KEY.format(id=conversation_id),
                self.EVENTS_KEY.format(id=conversation_id),
            ]

            async with client.pipeline() as pipe:
                for key in keys:
                    await pipe.expire(key, ttl_seconds)
                await pipe.execute()

            return True
        except Exception as e:
            raise StorageError(f"Failed to extend TTL: {e}")

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete all conversation data."""
        try:
            client = self._get_client()

            keys = [
                self.HISTORY_KEY.format(id=conversation_id),
                self.STATE_KEY.format(id=conversation_id),
                self.DRAFT_KEY.format(id=conversation_id),
                self.EVENTS_KEY.format(id=conversation_id),
            ]

            await client.delete(*keys)
            return True
        except Exception as e:
            raise StorageError(f"Failed to delete conversation: {e}")

    async def exists(self, conversation_id: str) -> bool:
        """Check if conversation exists."""
        try:
            client = self._get_client()
            key = self.STATE_KEY.format(id=conversation_id)
            return await client.exists(key) > 0
        except Exception as e:
            raise StorageError(f"Failed to check existence: {e}")

    # Clarification-specific methods
    async def save_clarification_request(
        self, conversation_id: str, clarification_id: str, questions: list[str]
    ) -> bool:
        """Save a clarification request."""
        try:
            client = self._get_client()
            key = self.CLARIFY_REQUEST_KEY.format(
                conv_id=conversation_id, clarify_id=clarification_id
            )
            await client.set(key, json.dumps(questions), ex=self._default_ttl)
            return True
        except Exception as e:
            raise StorageError(f"Failed to save clarification request: {e}")

    async def save_clarification_response(
        self, conversation_id: str, clarification_id: str, response: str
    ) -> bool:
        """Save a clarification response."""
        try:
            client = self._get_client()
            key = self.CLARIFY_RESPONSE_KEY.format(
                conv_id=conversation_id, clarify_id=clarification_id
            )
            await client.set(key, response, ex=self._default_ttl)
            return True
        except Exception as e:
            raise StorageError(f"Failed to save clarification response: {e}")

    async def get_clarification_response(
        self, conversation_id: str, clarification_id: str
    ) -> Optional[str]:
        """Get a clarification response."""
        try:
            client = self._get_client()
            key = self.CLARIFY_RESPONSE_KEY.format(
                conv_id=conversation_id, clarify_id=clarification_id
            )
            return await client.get(key)
        except Exception as e:
            raise StorageError(f"Failed to get clarification response: {e}")

    # Event stream methods
    async def add_event(
        self, conversation_id: str, event_type: str, payload: dict
    ) -> str:
        """Add event to Redis stream."""
        try:
            client = self._get_client()
            key = self.EVENTS_KEY.format(id=conversation_id)

            event_data = {
                "type": event_type,
                "payload": json.dumps(payload),
            }

            event_id = await client.xadd(key, event_data)
            await client.expire(key, self._default_ttl)
            return event_id
        except Exception as e:
            raise StorageError(f"Failed to add event: {e}")

    async def get_events_since(
        self, conversation_id: str, last_id: str = "0"
    ) -> list[dict]:
        """Get events from stream since given ID."""
        try:
            client = self._get_client()
            key = self.EVENTS_KEY.format(id=conversation_id)

            events = await client.xread({key: last_id}, block=0, count=100)
            if not events:
                return []

            result = []
            for _, messages in events:
                for event_id, data in messages:
                    result.append(
                        {
                            "id": event_id,
                            "type": data["type"],
                            "payload": json.loads(data["payload"]),
                        }
                    )
            return result
        except Exception as e:
            raise StorageError(f"Failed to get events: {e}")
