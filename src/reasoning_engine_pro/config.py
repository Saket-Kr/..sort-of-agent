"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Any, Literal

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Maps legacy env var / constructor names to their new field names.
_LEGACY_LLM_FIELD_MAP: dict[str, str] = {
    "llm_provider": "planner_llm_provider",
    "llm_base_url": "planner_llm_base_url",
    "llm_api_key": "planner_llm_api_key",
    "llm_model_name": "planner_llm_model_name",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @model_validator(mode="before")
    @classmethod
    def _remap_legacy_llm_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Accept old LLM_* env vars / kwargs and remap to PLANNER_LLM_*."""
        for old_name, new_name in _LEGACY_LLM_FIELD_MAP.items():
            if old_name in data and new_name not in data:
                data[new_name] = data.pop(old_name)
            elif old_name in data:
                data.pop(old_name)
        return data

    # Planner LLM Configuration (primary reasoning model)
    planner_llm_provider: Literal["vllm", "openai"] = "vllm"
    planner_llm_base_url: str = "http://localhost:8000/v1"
    planner_llm_api_key: str = ""
    planner_llm_model_name: str = "default-model"

    # Validator LLM Configuration (cheaper model for validation, referencing, summarization, job naming)
    validator_llm_base_url: str = "http://localhost:8000/v1"
    validator_llm_api_key: str = ""
    validator_llm_model_name: str = "default-model"

    # Feature Flags
    query_refinement_mode: Literal["separate", "inline", "disabled"] = "disabled"
    enable_referencing: bool = False
    token_summarization_limit: int = 100000

    # Heartbeat
    heartbeat_interval_seconds: int = 20
    heartbeat_max_missed: int = 3

    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_ttl_seconds: int = 86400  # 1 day

    # Search Services
    web_search_api_url: str = "https://api.perplexity.ai"
    web_search_api_key: str = ""
    web_search_model: str = "llama-3.1-sonar-small-128k-online"
    web_search_max_tokens: int = 1024
    task_block_search_url: str = "http://localhost:8000/api/task-blocks"
    task_block_search_api_key: str = ""

    # Search Backend Selection
    web_search_backend: str = "perplexity"  # "perplexity" or "integrated"
    task_block_search_backend: str = "legacy"  # "legacy" or "integrated"

    # Integrated Search Endpoint (used when backend = "integrated")
    integrated_search_url: str = ""
    integrated_search_api_key: str = ""
    integrated_search_timeout: float = 30.0

    # Integrated Web Search Params
    integrated_web_search_max_results: int = 3
    integrated_web_search_model_type: str = "big"

    # Integrated Task Block Search Params
    integrated_task_block_search_type: str = "llm"  # "llm" or "elastic"
    integrated_task_block_is_reason_required: bool = True
    integrated_elastic_task_block_size: int = 5

    # Planner Configuration
    planner_max_iterations: int = 10

    # Server Configuration
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    rest_port: int = 8090
    max_concurrent_connections: int = 50

    # Observability
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    log_level: str = "INFO"

    # Backward-compatible aliases — existing code using settings.llm_provider still works.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_provider(self) -> str:
        return self.planner_llm_provider

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_base_url(self) -> str:
        return self.planner_llm_base_url

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_api_key(self) -> str:
        return self.planner_llm_api_key

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_model_name(self) -> str:
        return self.planner_llm_model_name


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
