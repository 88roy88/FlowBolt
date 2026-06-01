from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, WebSocketException, status
from pydantic import BaseModel, ConfigDict, model_validator

from flow44.config import settings
from flow44.db.project import Project
from flow44.db.project import get_project as db_get_project
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import SandboxNotFoundError, sandbox_manager

logger = logging.getLogger(__name__)


def _claim_with_suffix(payload: dict[str, object], suffix: str) -> str | None:
    """Return the first claim value whose key ends with ``suffix`` (e.g. ``/UniqueID``)."""
    for key, value in payload.items():
        if isinstance(key, str) and key.endswith(suffix) and isinstance(value, str) and value.strip():
            return value.strip()
    return None


class TokenPayload(BaseModel):
    """JWT payload. Custom claims arrive URL-prefixed (e.g. ``.../UniqueID``);
    the validator surfaces them as clean attributes. Unknown claims pass through."""

    model_config = ConfigDict(extra="allow")

    iss: str | None = None
    exp: int | None = None
    unique_id: str | None = None
    given_name: str | None = None
    surname: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _surface_url_claims(cls, data: dict[str, object]) -> dict[str, object]:
        return data | {
            "unique_id": _claim_with_suffix(data, "/UniqueID"),
            "given_name": _claim_with_suffix(data, "/givenname"),
            "surname": _claim_with_suffix(data, "/surname"),
        }


def get_authorization_header(
    authorization: str | None = Header(None, alias="Authorization"),
    flow44_token: str | None = Cookie(None),
) -> str | None:
    raw = (authorization or flow44_token or "").strip()
    if not raw:
        return None
    return raw[7:].strip() if raw.lower().startswith("bearer ") else raw


TokenDep = Annotated[str | None, Depends(get_authorization_header)]


def decode_token(token: str) -> TokenPayload | None:
    """Verify signature and parse the payload into a TokenPayload. Returns None on any failure."""
    try:
        decoded = jwt.decode(
            token,
            settings.AUTH_JWT_PUBLIC_KEY,
            algorithms=[settings.AUTH_JWT_ALGORITHM],
        )
    except jwt.PyJWTError as e:
        logger.debug("JWT decode failed: %s", e)
        return None
    return TokenPayload.model_validate(decoded)


def get_user_id(token: TokenDep) -> str:
    """Resolve a raw token to a user_id under the dual-mode policy."""
    if not token:
        if settings.AUTH_REQUIRE_JWT:
            raise HTTPException(status_code=401, detail="Authorization required")
        return "611noat"

    is_jwt = token.count(".") == 2

    if is_jwt:
        payload = decode_token(token)
        if payload and payload.unique_id:
            return payload.unique_id
        if not settings.AUTH_REQUIRE_JWT:
            return token
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        raise HTTPException(status_code=401, detail="Token missing user identification")

    if settings.AUTH_REQUIRE_JWT:
        raise HTTPException(status_code=401, detail="JWT token required")

    return token


UserDep = Annotated[str, Depends(get_user_id)]


async def get_project(project_id: str, user_id: UserDep) -> Project:
    project = await db_get_project(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


ProjectDep = Annotated[Project, Depends(get_project)]


async def get_ws_user_id(flow44_token: Annotated[str | None, Cookie()] = None) -> str:
    """WS variant of get_user_id: raises WebSocketException so FastAPI rejects the handshake before accept."""
    try:
        return get_user_id(flow44_token)
    except HTTPException:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from None


WsUserDep = Annotated[str, Depends(get_ws_user_id)]


async def get_ws_project(project_id: str, user_id: WsUserDep) -> Project:
    try:
        return await get_project(project_id, user_id)
    except HTTPException:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from None


WsProjectDep = Annotated[Project, Depends(get_ws_project)]


WS_SANDBOX_NOT_FOUND = 4404


async def get_sandbox(project: ProjectDep) -> PnpmSandbox:
    try:
        return sandbox_manager.get_sandbox(project.id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project.id}") from None


SandboxDep = Annotated[PnpmSandbox, Depends(get_sandbox)]


async def get_ws_sandbox(project: WsProjectDep) -> PnpmSandbox:
    try:
        return sandbox_manager.get_sandbox(project.id)
    except SandboxNotFoundError:
        raise WebSocketException(code=WS_SANDBOX_NOT_FOUND, reason="Sandbox not found") from None


WsSandboxDep = Annotated[PnpmSandbox, Depends(get_ws_sandbox)]
