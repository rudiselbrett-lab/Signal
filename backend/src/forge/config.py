"""Application configuration.

Single source of truth for environment configuration. Fail-fast: the app
refuses to boot with invalid settings rather than failing later at runtime.
"""

from functools import lru_cache
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

# MVP is single-user: every table carries user_id so multi-user is a schema
# no-op later, but auth resolves to this fixed identity for now.
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORGE_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://forge:forge@localhost:5432/forge"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Model ids are config, never code.
    llm_pipeline_model: str = "claude-sonnet-5"
    llm_coach_model: str = "claude-opus-4-8"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536

    discovery_interval_hours: int = 2
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
