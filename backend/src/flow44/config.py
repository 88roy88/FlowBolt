"""Application configuration using pydantic-settings."""

import os
from pathlib import Path
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_WORKSPACE = str(_BACKEND_ROOT / "data" / "workspaces")
_DEFAULT_TEMPLATE = str(_BACKEND_ROOT / "pnpm-project-template")


class Flow44BaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIB_", env_file=".env", extra="ignore")


class SandboxSettings(Flow44BaseSettings):
    WORKSPACE_BASE_DIR: str = _DEFAULT_WORKSPACE
    TEMPLATE_DIR: str = _DEFAULT_TEMPLATE
    SANDBOX_PORT_RANGE_START: int = 3101
    SANDBOX_PORT_RANGE_END: int = 4101
    NSJAIL_BIN: str = "/usr/bin/nsjail"
    MAX_COMMAND_TIMEOUT: int = 60
    SANDBOX_MEMORY_LIMIT_MB: int = 512
    SANDBOX_PID_LIMIT: int = 256
    SANDBOX_DISABLE_CGROUPS: bool = False
    PNPM_STORE_DIR: str = "/var/lib/ai-builder/workspaces/.pnpm-store"
    SANDBOX_MODE: Literal["local", "namespaced"] = "local"
    # Public base URL of this backend, used in HTML exports so API calls work standalone.
    EXPORT_API_BASE_URL: str = "http://localhost:8000"


class AIModelSettings(Flow44BaseSettings):
    AI_MODEL: str = "qwen/qwen3-coder-30b-a3b-instruct"
    # Base URL for OpenAI-compatible endpoints (vLLM, Ollama, OpenRouter, etc.)
    AI_BASE_URL: str = "http://ai-builder-models.com/openai/v1"
    AI_API_KEY: str = "default"


class SearchIndexSettings(Flow44BaseSettings):
    SEARCH_INDEX_MAX_FILE_SIZE_MB: int = 1  # Max size per file to index (MB)
    SEARCH_INDEX_MAX_TOTAL_SIZE_MB: int = 20  # Max total indexed content per project (MB)
    SEARCH_INDEX_CACHE_TTL_SECONDS: int = 5  # How long to cache index before rebuilding


class FlapiSettings(Flow44BaseSettings):
    # FLAPI base URL. In dev you can point to the local mock (default).
    FLAPI_BASE_URL: str = "http://localhost:6000"
    FLAPI_VERIFY_SSL: bool = True


class S3Settings(Flow44BaseSettings):
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None
    S3_CACHE_TTL: int = 3600


class LangfuseSettings(Flow44BaseSettings):
    # Langfuse (optional — set public/secret key to enable)
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    def model_post_init(self, __context: Any) -> None:
        """Propagate Langfuse credentials to os.environ so the SDK can read them."""
        if self.LANGFUSE_PUBLIC_KEY and self.LANGFUSE_SECRET_KEY:
            os.environ["LANGFUSE_PUBLIC_KEY"] = self.LANGFUSE_PUBLIC_KEY
            os.environ["LANGFUSE_SECRET_KEY"] = self.LANGFUSE_SECRET_KEY
            os.environ["LANGFUSE_HOST"] = self.LANGFUSE_HOST


class Settings(
    SandboxSettings,
    AIModelSettings,
    SearchIndexSettings,
    FlapiSettings,
    S3Settings,
    LangfuseSettings,
    Flow44BaseSettings,
):
    DATABASE_URL: str = "sqlite:///./ai_builder.db"


settings = Settings()
