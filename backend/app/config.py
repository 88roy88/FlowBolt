"""Application configuration using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings

_DEFAULT_WORKSPACE = str(Path(__file__).resolve().parent.parent / "data" / "workspaces")


class Settings(BaseSettings):
    """Global application settings, loaded from environment variables."""

    WORKSPACE_BASE_DIR: str = _DEFAULT_WORKSPACE
    SANDBOX_PORT_RANGE_START: int = 3001
    SANDBOX_PORT_RANGE_END: int = 3100
    NSJAIL_BIN: str = "/usr/bin/nsjail"
    AI_MODEL: str = "bedrock/anthropic.claude-sonnet-4-20250514"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DATABASE_URL: str = "sqlite:///./ai_builder.db"
    MAX_COMMAND_TIMEOUT: int = 60
    SANDBOX_MEMORY_LIMIT_MB: int = 512
    SANDBOX_PID_LIMIT: int = 256

    # Langfuse (optional — set public/secret key to enable)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = {"env_prefix": "AIB_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
