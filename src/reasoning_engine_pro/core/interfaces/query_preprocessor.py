"""Query preprocessor interface."""

from abc import ABC, abstractmethod

from ..schemas.messages import ChatMessage, UserInfo


class IQueryPreprocessor(ABC):
    """Preprocesses user queries before they reach the planner."""

    @abstractmethod
    async def preprocess(
        self,
        message: str,
        history: list[ChatMessage],
        user_info: UserInfo | None = None,
    ) -> str:
        """Return the refined/augmented message. May be unchanged."""
        ...
