"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings, loaded from environment variables."""

    WORKSPACE_BASE_DIR: str = "/var/lib/ai-builder/workspaces"
    SANDBOX_PORT_RANGE_START: int = 3001
    SANDBOX_PORT_RANGE_END: int = 3100
    NSJAIL_BIN: str = "/usr/bin/nsjail"
    AI_MODEL: str = "bedrock/anthropic.claude-sonnet-4-20250514"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DATABASE_URL: str = "sqlite:///./ai_builder.db"
    MAX_COMMAND_TIMEOUT: int = 60
    SANDBOX_MEMORY_LIMIT_MB: int = 512
    SANDBOX_PID_LIMIT: int = 256

    model_config = {"env_prefix": "AIB_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
