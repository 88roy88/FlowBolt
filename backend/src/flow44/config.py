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
    SANDBOX_PORT_RANGE_START: int = 3501
    SANDBOX_PORT_RANGE_END: int = 4501
    NSJAIL_BIN: str = "/usr/bin/nsjail"
    MAX_COMMAND_TIMEOUT: int = 60
    SANDBOX_MEMORY_LIMIT_MB: int = 512
    SANDBOX_PID_LIMIT: int = 256
    SANDBOX_DISABLE_CGROUPS: bool = False
    PNPM_STORE_DIR: str = "/var/lib/flow-44/workspaces/.pnpm-store"
    SANDBOX_MODE: Literal["local", "namespaced"] = "local"
    # Public base URL of this backend, used in HTML exports so API calls work standalone.
    EXPORT_API_BASE_URL: str = "http://localhost:8000"
    # SSO config injected into generated apps' vite.config.ts at scaffold time
    SANDBOX_AUTH_PROVIDER_URL: str = "http://localhost:6001/sso"
    SANDBOX_AUTH_STORAGE_KEY: str = "Auth"
    SANDBOX_AUTH_USE_IFRAME: bool = True
    SANDBOX_AUTH_POST_MESSAGE_TARGET: str = "*"


class DatabaseSettings(Flow44BaseSettings):
    DB_SCHEME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True


class AIModelSettings(Flow44BaseSettings):
    AI_MODEL: str = "qwen/qwen3-coder-30b-a3b-instruct"
    # Base URL for OpenAI-compatible endpoints (vLLM, Ollama, OpenRouter, etc.)
    AI_BASE_URL: str = "http://flow-44-models.com/openai/v1"
    AI_API_KEY: str = "default"


class SearchIndexSettings(Flow44BaseSettings):
    SEARCH_INDEX_MAX_FILE_SIZE_MB: int = 1  # Max size per file to index (MB)
    SEARCH_INDEX_MAX_TOTAL_SIZE_MB: int = 20  # Max total indexed content per project (MB)
    SEARCH_INDEX_CACHE_TTL_SECONDS: int = 5  # How long to cache index before rebuilding


class AuthSettings(Flow44BaseSettings):
    # JWT public key or HMAC secret used to verify token signatures (required)
    AUTH_JWT_PUBLIC_KEY: str
    # JWT algorithm (default: HS256 for HMAC, use RS256 for RSA)
    AUTH_JWT_ALGORITHM: str = "RS256"
    # Require JWT format (vs allowing opaque tokens)
    AUTH_REQUIRE_JWT: bool = False


class FlapiSettings(Flow44BaseSettings):
    # FLAPI base URL. In dev you can point to the local mock (default).
    FLAPI_BASE_URL: str = "http://localhost:6001"
    FLAPI_VERIFY_SSL: bool = True


class S3Settings(Flow44BaseSettings):
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None
    S3_CACHE_TTL: int = 3600
    S3_STORAGE_CLASS: str = "STANDARD_IA"


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
    DatabaseSettings,
    AIModelSettings,
    SearchIndexSettings,
    AuthSettings,
    FlapiSettings,
    S3Settings,
    LangfuseSettings,
    Flow44BaseSettings,
):
    pass


settings = Settings()
