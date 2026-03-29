"""Application configuration using pydantic-settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_WORKSPACE = str(_BACKEND_ROOT / "data" / "workspaces")
_DEFAULT_TEMPLATE = str(_BACKEND_ROOT / "pnpm-project-template")


class Settings(BaseSettings):
    """Global application settings, loaded from environment variables."""

    WORKSPACE_BASE_DIR: str = _DEFAULT_WORKSPACE
    TEMPLATE_DIR: str = _DEFAULT_TEMPLATE
    SANDBOX_PORT_RANGE_START: int = 3101
    SANDBOX_PORT_RANGE_END: int = 4101
    NSJAIL_BIN: str = "/usr/bin/nsjail"
    AI_MODEL: str = "bedrock/us.anthropic.claude-sonnet-4-6"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DATABASE_URL: str
    MAX_COMMAND_TIMEOUT: int = 60
    SANDBOX_MEMORY_LIMIT_MB: int = 512
    SANDBOX_PID_LIMIT: int = 256
    SANDBOX_DISABLE_CGROUPS: bool = False
    PNPM_STORE_DIR: str = "/var/lib/ai-builder/workspaces/.pnpm-store"
    SANDBOX_MODE: str = "local"  # "local" or "namespaced"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True

    # External APIs
    # FLAPI base URL. In dev you can point to the local mock (default).
    FLAPI_BASE_URL: str = "http://localhost:4000"
    VERIFY_FLAPI_SSL: bool = True
    # Public base URL of this backend, used in HTML exports so API calls work standalone.
    EXPORT_API_BASE_URL: str = "http://localhost:8000"

    # S3 / Object Storage
    S3_ENDPOINT_URL: str = Field(default="", validation_alias="S3_ENDPOINT_URL")
    S3_ACCESS_KEY: str = Field(default="", validation_alias="S3_ACCESS_KEY")
    S3_SECRET_KEY: str = Field(default="", validation_alias="S3_SECRET_KEY")
    S3_BUCKET_NAME: str = Field(default="", validation_alias="S3_BUCKET_NAME")
    S3_CACHE_TTL: int = Field(default=3600, validation_alias="S3_CACHE_TTL")
    S3_STORAGE_CLASS: str = Field(default="STANDARD_IA", validation_alias="S3_STORAGE_CLASS")

    # Langfuse (optional — set public/secret key to enable)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(env_prefix="AIB_", env_file=".env", extra="ignore")


settings = Settings()
