"""Redis storage implementation."""

import functools
import json
from typing import Optional

import redis.asyncio as redis

from ...core.exceptions import StorageError
from ...core.interfaces.storage import IConversationStorage
from ...core.schemas.messages import ChatMessage, ConversationState


def _storage_operation(operation_name: str):
    """Decorator that wraps async storage methods with consistent error handling."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except StorageError:
                raise
            except Exception as e:
                raise StorageError(f"Failed to {operation_name}: {e}")

        return wrapper

    return decorator


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
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> redis.Redis:
        """Get Redis client, raising if not connected."""
        if self._client is None:
            raise StorageError("Redis client not connected. Call connect() first.")
        return self._client

    @_storage_operation("save message")
    async def save_message(self, conversation_id: str, message: ChatMessage) -> bool:
        """Save a message to conversation history."""
        client = self._get_client()
        key = self.HISTORY_KEY.format(id=conversation_id)
        message_json = message.model_dump_json()

        async with client.pipeline() as pipe:
            await pipe.rpush(key, message_json)
            await pipe.expire(key, self._default_ttl)
            await pipe.execute()

        return True

    @_storage_operation("get history")
    async def get_history(
        self, conversation_id: str, max_messages: Optional[int] = None
    ) -> list[ChatMessage]:
        """Get conversation history."""
        client = self._get_client()
        key = self.HISTORY_KEY.format(id=conversation_id)

        if max_messages:
            messages_json = await client.lrange(key, -max_messages, -1)
        else:
            messages_json = await client.lrange(key, 0, -1)

        messages = [
            ChatMessage.model_validate_json(msg_json) for msg_json in messages_json
        ]

        await client.expire(key, self._default_ttl)
        return messages

    @_storage_operation("save state")
    async def save_state(self, conversation_id: str, state: ConversationState) -> bool:
        """Save conversation state."""
        client = self._get_client()
        key = self.STATE_KEY.format(id=conversation_id)
        state_json = state.model_dump_json()
        await client.set(key, state_json, ex=self._default_ttl)
        return True

    @_storage_operation("get state")
    async def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Get conversation state."""
        client = self._get_client()
        key = self.STATE_KEY.format(id=conversation_id)
        state_json = await client.get(key)
        if state_json is None:
            return None
        await client.expire(key, self._default_ttl)
        return ConversationState.model_validate_json(state_json)

    @_storage_operation("save draft")
    async def save_draft(self, conversation_id: str, draft: str) -> bool:
        """Save draft response."""
        client = self._get_client()
        key = self.DRAFT_KEY.format(id=conversation_id)
        await client.set(key, draft, ex=self._default_ttl)
        return True

    @_storage_operation("get draft")
    async def get_draft(self, conversation_id: str) -> Optional[str]:
        """Get saved draft response."""
        client = self._get_client()
        key = self.DRAFT_KEY.format(id=conversation_id)
        return await client.get(key)

    @_storage_operation("extend TTL")
    async def extend_ttl(self, conversation_id: str, ttl_seconds: int) -> bool:
        """Extend TTL for all conversation data."""
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

    @_storage_operation("delete conversation")
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete all conversation data."""
        client = self._get_client()
        keys = [
            self.HISTORY_KEY.format(id=conversation_id),
            self.STATE_KEY.format(id=conversation_id),
            self.DRAFT_KEY.format(id=conversation_id),
            self.EVENTS_KEY.format(id=conversation_id),
        ]
        await client.delete(*keys)
        return True

    @_storage_operation("check existence")
    async def exists(self, conversation_id: str) -> bool:
        """Check if conversation exists."""
        client = self._get_client()
        key = self.STATE_KEY.format(id=conversation_id)
        return await client.exists(key) > 0

    @_storage_operation("save clarification request")
    async def save_clarification_request(
        self, conversation_id: str, clarification_id: str, questions: list[str]
    ) -> bool:
        """Save a clarification request."""
        client = self._get_client()
        key = self.CLARIFY_REQUEST_KEY.format(
            conv_id=conversation_id, clarify_id=clarification_id
        )
        await client.set(key, json.dumps(questions), ex=self._default_ttl)
        return True

    @_storage_operation("save clarification response")
    async def save_clarification_response(
        self, conversation_id: str, clarification_id: str, response: str
    ) -> bool:
        """Save a clarification response."""
        client = self._get_client()
        key = self.CLARIFY_RESPONSE_KEY.format(
            conv_id=conversation_id, clarify_id=clarification_id
        )
        await client.set(key, response, ex=self._default_ttl)
        return True

    @_storage_operation("get clarification response")
    async def get_clarification_response(
        self, conversation_id: str, clarification_id: str
    ) -> Optional[str]:
        """Get a clarification response."""
        client = self._get_client()
        key = self.CLARIFY_RESPONSE_KEY.format(
            conv_id=conversation_id, clarify_id=clarification_id
        )
        return await client.get(key)

    @_storage_operation("add event")
    async def add_event(
        self, conversation_id: str, event_type: str, payload: dict
    ) -> str:
        """Add event to Redis stream."""
        client = self._get_client()
        key = self.EVENTS_KEY.format(id=conversation_id)
        event_data = {
            "type": event_type,
            "payload": json.dumps(payload),
        }
        event_id = await client.xadd(key, event_data)
        await client.expire(key, self._default_ttl)
        return event_id

    @_storage_operation("get events")
    async def get_events_since(
        self, conversation_id: str, last_id: str = "0"
    ) -> list[dict]:
        """Get events from stream since given ID."""
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
