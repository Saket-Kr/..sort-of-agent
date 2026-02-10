"""FastAPI dependency injection."""

from functools import lru_cache
from typing import Optional

from ..agents.few_shot import FewShotRetriever
from ..agents.job_name import JobNameGenerator
from ..agents.orchestrator import ConversationOrchestrator
from ..agents.planner import PlannerAgent
from ..agents.validator import WorkflowValidator
from ..config import Settings, get_settings
from ..core.interfaces.event_emitter import IEventEmitter
from ..core.interfaces.storage import IConversationStorage
from ..llm.factory import LLMProviderFactory
from ..observability.tracing import LangfuseTracer
from ..services.storage.memory import InMemoryStorage
from ..services.storage.redis import RedisStorage
from ..tools.factory import ToolFactory


class Dependencies:
    """Container for application dependencies."""

    _instance: Optional["Dependencies"] = None

    def __init__(self, settings: Settings):
        self.settings = settings
        self._storage: Optional[IConversationStorage] = None
        self._orchestrator: Optional[ConversationOrchestrator] = None
        self._tracer: Optional[LangfuseTracer] = None

    @classmethod
    def get_instance(cls, settings: Optional[Settings] = None) -> "Dependencies":
        """Get or create singleton instance."""
        if cls._instance is None:
            if settings is None:
                settings = get_settings()
            cls._instance = cls(settings)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    async def get_storage(self) -> IConversationStorage:
        """Get storage instance."""
        if self._storage is None:
            if self.settings.redis_url:
                self._storage = RedisStorage(
                    redis_url=self.settings.redis_url,
                    default_ttl=self.settings.redis_ttl_seconds,
                )
                await self._storage.connect()
            else:
                self._storage = InMemoryStorage(
                    default_ttl=self.settings.redis_ttl_seconds
                )
        return self._storage

    def get_tracer(self) -> LangfuseTracer:
        """Get Langfuse tracer."""
        if self._tracer is None:
            self._tracer = LangfuseTracer(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host,
            )
        return self._tracer

    async def get_orchestrator(
        self, event_emitter: Optional[IEventEmitter] = None
    ) -> ConversationOrchestrator:
        """Get orchestrator instance."""
        storage = await self.get_storage()

        # Create LLM provider
        llm = LLMProviderFactory.create_from_settings(self.settings)

        # Create tools
        tool_registry = ToolFactory.create_all(self.settings)

        # Create planner
        planner = PlannerAgent(
            llm_provider=llm,
            tool_registry=tool_registry,
            event_emitter=event_emitter,
            max_iterations=self.settings.planner_max_iterations,
        )

        # Create validator
        validator = WorkflowValidator(event_emitter=event_emitter)

        # Create job name generator
        job_name_gen = JobNameGenerator()

        # Create few-shot retriever
        few_shot = FewShotRetriever.from_settings(self.settings)

        return ConversationOrchestrator(
            storage=storage,
            planner=planner,
            validator=validator,
            job_name_generator=job_name_gen,
            few_shot_retriever=few_shot,
            event_emitter=event_emitter,
        )

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._storage and isinstance(self._storage, RedisStorage):
            await self._storage.disconnect()

        if self._tracer:
            self._tracer.shutdown()


# FastAPI dependency functions
async def get_dependencies() -> Dependencies:
    """Get dependencies container."""
    return Dependencies.get_instance()


async def get_storage(deps: Dependencies = None) -> IConversationStorage:
    """Get storage dependency."""
    if deps is None:
        deps = Dependencies.get_instance()
    return await deps.get_storage()


async def get_settings_dep() -> Settings:
    """Get settings dependency."""
    return get_settings()
