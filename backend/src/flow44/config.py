"""Application configuration using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_WORKSPACE = str(_BACKEND_ROOT / "data" / "workspaces")
_DEFAULT_TEMPLATE = str(_BACKEND_ROOT / "pnpm-project-template")


# TODO: split to smaller config classes, e.g. SandboxSettings, AIModelSettings, etc.
class Settings(BaseSettings):
    WORKSPACE_BASE_DIR: str = _DEFAULT_WORKSPACE
    TEMPLATE_DIR: str = _DEFAULT_TEMPLATE
    SANDBOX_PORT_RANGE_START: int = 3101
    SANDBOX_PORT_RANGE_END: int = 4101
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

    # Search Index Settings
    SEARCH_INDEX_MAX_FILE_SIZE_MB: int = 1  # Max size per file to index (MB)
    SEARCH_INDEX_MAX_TOTAL_SIZE_MB: int = 20  # Max total indexed content per project (MB)
    SEARCH_INDEX_CACHE_TTL_SECONDS: int = 5  # How long to cache index before rebuilding

    # External APIs
    # FLAPI base URL. In dev you can point to the local mock (default).
    FLAPI_BASE_URL: str = "http://localhost:4000"
    FLAPI_VERIFY_SSL: bool = True
    # Public base URL of this backend, used in HTML exports so API calls work standalone.
    EXPORT_API_BASE_URL: str = "http://localhost:8000"

    # S3 / Object Storage
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = ""
    S3_CACHE_TTL: int = 3600

    # TODO: make | None instead of empty string?
    # Langfuse (optional — set public/secret key to enable)
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(env_prefix="AIB_", env_file=".env", extra="ignore")


settings = Settings()
