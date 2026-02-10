"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM Configuration
    llm_provider: Literal["vllm", "openai"] = "vllm"
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = ""
    llm_model_name: str = "default-model"

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
