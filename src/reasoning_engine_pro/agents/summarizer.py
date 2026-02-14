"""Message summarizer — condenses conversation history when token limits approach."""

from ..core.enums import MessageRole
from ..core.interfaces.llm_provider import ILLMProvider
from ..core.schemas.messages import ChatMessage
from ..observability.logger import get_logger
from .prompts.loader import PromptLoader

logger = get_logger(__name__)

_loader = PromptLoader()


class MessageSummarizer:
    """Summarizes conversation history using an LLM.

    Preserves user clarifications exactly. Trims agent reasoning
    and tool output to essential conclusions.
    """

    def __init__(self, llm_provider: ILLMProvider):
        self._llm = llm_provider

    async def summarize(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Summarize a list of messages into a condensed form.

        Returns a list containing the system message (if present) plus
        a single summary message.
        """
        if len(messages) <= 2:
            return messages

        system_prompt = _loader.load("summarizer_system")

        # Build conversation text for summarization
        conversation_parts: list[str] = []
        system_msg: ChatMessage | None = None

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_msg = msg
                continue
            role_label = msg.role.value.capitalize()
            conversation_parts.append(f"{role_label}: {msg.content or ''}")

        conversation_text = "\n\n".join(conversation_parts)

        try:
            summary_response = await self._llm.generate(
                messages=[
                    ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                    ChatMessage(
                        role=MessageRole.USER,
                        content=f"Summarize this conversation:\n\n{conversation_text}",
                    ),
                ],
                temperature=0.1,
            )

            summary_text = summary_response.content or conversation_text

            result: list[ChatMessage] = []
            if system_msg:
                result.append(system_msg)
            result.append(
                ChatMessage(
                    role=MessageRole.USER,
                    content=f"[Conversation Summary]\n{summary_text}",
                )
            )

            logger.info(
                "Conversation summarized",
                original_count=len(messages),
                summary_length=len(summary_text),
            )
            return result

        except Exception as e:
            logger.warning("Summarization failed, keeping original messages", error=str(e))
            return messages
