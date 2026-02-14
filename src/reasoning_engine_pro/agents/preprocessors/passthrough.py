"""Passthrough preprocessor — returns the message unchanged."""

from ...core.interfaces.query_preprocessor import IQueryPreprocessor
from ...core.schemas.messages import ChatMessage, UserInfo


class PassthroughPreprocessor(IQueryPreprocessor):
    """No-op preprocessor. Zero overhead when query refinement is disabled."""

    async def preprocess(
        self,
        message: str,
        history: list[ChatMessage],
        user_info: UserInfo | None = None,
    ) -> str:
        return message
