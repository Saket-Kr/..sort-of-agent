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
    task_block_search_url: str = "http://localhost:8000/api/task-blocks"
    task_block_search_api_key: str = ""

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
