"""Storage interface."""

from abc import ABC, abstractmethod
from typing import Optional

from ..schemas.messages import ChatMessage, ConversationState


class IConversationStorage(ABC):
    """Abstract interface for conversation storage."""

    @abstractmethod
    async def save_message(self, conversation_id: str, message: ChatMessage) -> bool:
        """
        Save a message to conversation history.

        Args:
            conversation_id: Unique conversation identifier
            message: Message to save

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    async def get_history(
        self, conversation_id: str, max_messages: Optional[int] = None
    ) -> list[ChatMessage]:
        """
        Get conversation history.

        Args:
            conversation_id: Unique conversation identifier
            max_messages: Optional limit on messages to retrieve

        Returns:
            List of messages in chronological order
        """
        ...

    @abstractmethod
    async def save_state(self, conversation_id: str, state: ConversationState) -> bool:
        """
        Save conversation state.

        Args:
            conversation_id: Unique conversation identifier
            state: Conversation state to save

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    async def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """
        Get conversation state.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Conversation state or None if not found
        """
        ...

    @abstractmethod
    async def save_draft(self, conversation_id: str, draft: str) -> bool:
        """
        Save draft response for resumption.

        Args:
            conversation_id: Unique conversation identifier
            draft: Draft response content

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    async def get_draft(self, conversation_id: str) -> Optional[str]:
        """
        Get saved draft response.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Draft content or None
        """
        ...

    @abstractmethod
    async def extend_ttl(self, conversation_id: str, ttl_seconds: int) -> bool:
        """
        Extend TTL for all conversation data.

        Args:
            conversation_id: Unique conversation identifier
            ttl_seconds: New TTL in seconds

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete all conversation data.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if successful
        """
        ...

    @abstractmethod
    async def exists(self, conversation_id: str) -> bool:
        """
        Check if conversation exists.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if conversation exists
        """
        ...
