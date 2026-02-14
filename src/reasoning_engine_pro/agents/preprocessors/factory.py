"""Query preprocessor factory."""

from ...config import Settings
from ...core.interfaces.event_emitter import IEventEmitter
from ...core.interfaces.llm_provider import ILLMProvider
from ...core.interfaces.query_preprocessor import IQueryPreprocessor
from .inline_refinement import InlineRefinementPreprocessor
from .passthrough import PassthroughPreprocessor
from .query_refinement import QueryRefinementPreprocessor


class QueryPreprocessorFactory:
    """Creates the correct preprocessor based on config."""

    @staticmethod
    def create(
        settings: Settings,
        llm_provider: ILLMProvider | None = None,
        event_emitter: IEventEmitter | None = None,
    ) -> IQueryPreprocessor:
        mode = settings.query_refinement_mode

        if mode == "separate":
            if llm_provider is None:
                raise ValueError("query_refinement_mode='separate' requires an LLM provider")
            return QueryRefinementPreprocessor(llm_provider, event_emitter)

        if mode == "inline":
            return InlineRefinementPreprocessor()

        return PassthroughPreprocessor()
