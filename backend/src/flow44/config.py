"""Application configuration using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_WORKSPACE = str(_BACKEND_ROOT / "data" / "workspaces")
_DEFAULT_TEMPLATE = str(_BACKEND_ROOT / "pnpm-project-template")


class Settings(BaseSettings):
    """Global application settings, loaded from environment variables."""

    WORKSPACE_BASE_DIR: str = _DEFAULT_WORKSPACE
    TEMPLATE_DIR: str = _DEFAULT_TEMPLATE
    SANDBOX_PORT_RANGE_START: int = 3001
    SANDBOX_PORT_RANGE_END: int = 3100
    NSJAIL_BIN: str = "/usr/bin/nsjail"
    AI_MODEL: str = "bedrock/us.anthropic.claude-sonnet-4-6"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DATABASE_URL: str = "sqlite:///./ai_builder.db"
    MAX_COMMAND_TIMEOUT: int = 60
    SANDBOX_MEMORY_LIMIT_MB: int = 512
    SANDBOX_PID_LIMIT: int = 256
    SANDBOX_DISABLE_CGROUPS: bool = False
    PNPM_STORE_DIR: str = "/var/lib/ai-builder/workspaces/.pnpm-store"
    SANDBOX_MODE: str = "local"  # "local" or "namespaced"

    # External APIs
    # Package API (FLAPI) base URL. In dev you can point to the local mock (default).
    PACKAGE_API_BASE_URL: str = "http://localhost:4000"
    # Public base URL of this backend, used in HTML exports so API calls work standalone.
    EXPORT_API_BASE_URL: str = ""

    # Langfuse (optional — set public/secret key to enable)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = {"env_prefix": "AIB_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
