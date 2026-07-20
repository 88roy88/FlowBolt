"""Application configuration using pydantic-settings."""

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import model_validator
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
    PNPM_STORE_DIR: str = "/var/lib/flow-44/.pnpm-store"
    NPM_REGISTRY: str = "https://registry.npmjs.org/"
    NPM_STRICT_SSL: bool = True
    NPM_AUDIT: bool = True
    SANDBOX_MODE: Literal["local", "namespaced"] = "local"
    AGENT_RUN_TIMEOUT: int = 1800  # whole-run budget
    AGENT_RUN_STALE_TIMEOUT: int = 60  # when a heartbeat is considered dead (beat=/4, sweep=/2)
    SANDBOX_IDLE_TTL_SECONDS: int = 5 * 60  # 5 minutes
    SANDBOX_IDLE_CHECK_INTERVAL_SECONDS: int = 60
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
    AI_BASE_URL: str | None = "http://flow-44-models.com/openai/v1"
    AI_API_KEY: str | None = "default"
    AI_REQUEST_TIMEOUT: int = 300

    # if ai_model starts with bedrock/ set base_url and api_key to None
    # (using pydantic v2's model_validator to allow dynamic defaults based on other fields)
    @model_validator(mode="before")
    def _set_bedrock_defaults(cls, values: dict[str, Any]) -> dict[str, Any]:
        ai_model = values.get("AI_MODEL", "")
        if ai_model.startswith("bedrock/"):
            values["AI_BASE_URL"] = None
            values["AI_API_KEY"] = None
        return values


class SearchIndexSettings(Flow44BaseSettings):
    SEARCH_INDEX_MAX_FILE_SIZE_MB: int = 1  # Max size per file to index (MB)
    SEARCH_INDEX_MAX_TOTAL_SIZE_MB: int = 20  # Max total indexed content per project (MB)
    SEARCH_INDEX_CACHE_TTL_SECONDS: int = 5  # How long to cache index before rebuilding


class AuthSettings(Flow44BaseSettings):
    # JWT public key / HMAC secret for verifying token signatures (required)
    AUTH_JWT_PUBLIC_KEY: str
    # JWT algorithm (default: HS256 for HMAC, use RS256 for RSA)
    AUTH_JWT_ALGORITHM: str = "RS256"
    # Name of the cookie carrying the auth token (must match the frontend's VITE_AUTH_COOKIE_NAME)
    AUTH_COOKIE_NAME: str = "flow44_token"
    # User IDs with system-admin privileges (can access all projects, invite platform users)
    SYSTEM_ADMIN_IDS: list[str] = []


class FlapiSettings(Flow44BaseSettings):
    # FLAPI base URL. In dev you can point to the local mock (default).
    FLAPI_BASE_URL: str = "http://localhost:6001"
    FLAPI_VERIFY_SSL: bool = True


class S3Settings(Flow44BaseSettings):
    S3_ENDPOINT_URL: str
    S3_USE_SSL: bool = True
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_NAME: str
    S3_CACHE_TTL: int = 3600
    S3_STORAGE_CLASS: str = "STANDARD_IA"


class LoggerSettings(Flow44BaseSettings):
    LOG_FILE_PATH: str | None = None


class OpikSettings(Flow44BaseSettings):
    # Opik (optional — set an API key to enable)
    OPIK_API_KEY: str | None = None
    OPIK_WORKSPACE: str | None = None
    OPIK_PROJECT_NAME: str = "flow44"
    OPIK_URL_OVERRIDE: str | None = None

    def model_post_init(self, __context: Any) -> None:
        """Propagate Opik credentials to os.environ so the SDK can read them."""
        if self.OPIK_API_KEY:
            os.environ["OPIK_API_KEY"] = self.OPIK_API_KEY
            if self.OPIK_WORKSPACE:
                os.environ["OPIK_WORKSPACE"] = self.OPIK_WORKSPACE
            os.environ["OPIK_PROJECT_NAME"] = self.OPIK_PROJECT_NAME
            if self.OPIK_URL_OVERRIDE:
                os.environ["OPIK_URL_OVERRIDE"] = self.OPIK_URL_OVERRIDE


class Settings(
    SandboxSettings,
    DatabaseSettings,
    AIModelSettings,
    SearchIndexSettings,
    AuthSettings,
    FlapiSettings,
    S3Settings,
    OpikSettings,
    LoggerSettings,
    Flow44BaseSettings,
):
    pass


settings = Settings()
