import logging
from contextvars import ContextVar
from typing import Annotated, Any

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, WebSocketException, status
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from flow44.auth.permissions import (
    Permission,
    Role,
    get_admin_permissions,
    get_owner_permissions,
    get_role_permissions,
    has_permission,
)
from flow44.config import settings
from flow44.db.platform_user import is_platform_user as db_is_platform_user
from flow44.db.platform_user_group import platform_group_ids
from flow44.db.project import Project
from flow44.db.project import get_project as db_get_project
from flow44.db.project_member import get_project_member
from flow44.db.project_member_group import list_project_groups
from flow44.integrations.adapi.client import adapi_client
from flow44.logging import _project_id as _log_project_id
from flow44.logging import _user_id as _log_user_id
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import sandbox_manager

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
    exp: int
    unique_id: str | None = None
    email: str | None = None
    given_name: str | None = None
    surname: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _surface_url_claims(cls, data: dict[str, object]) -> dict[str, object]:
        return data | {
            "unique_id": _claim_with_suffix(data, "/UniqueID"),
            "email": _claim_with_suffix(data, "/emailaddress"),
            "given_name": _claim_with_suffix(data, "/givenname"),
            "surname": _claim_with_suffix(data, "/surname"),
        }


def get_authorization_header(
    authorization: str | None = Header(None, alias="Authorization"),
    flow44_token: str | None = Cookie(None, alias=settings.AUTH_COOKIE_NAME),
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
    try:
        return TokenPayload.model_validate(decoded)
    except ValidationError as e:
        logger.debug("Token payload missing required claims: %s", e)
        return None


def validate_token(token: TokenDep) -> TokenPayload:
    """Require a valid signed token; no user_id claim needed."""
    if not token:
        raise HTTPException(status_code=401, detail="Authorization required")

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


def get_user_id(token: TokenDep) -> str:
    """Resolve a token to a user_id; a valid signed JWT with an ``/emailaddress`` claim is required."""
    payload = validate_token(token)
    user_id = payload.email
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user identification")

    _log_user_id.set(user_id)
    return user_id


UserDep = Annotated[str, Depends(get_user_id)]


def is_admin(user_id: str) -> bool:
    return user_id in settings.SYSTEM_ADMIN_IDS


async def resolve_group_permissions(project_id: str, user_id: str) -> set[Permission]:
    grants = await list_project_groups(project_id)
    if not grants:
        return set()

    user_group_ids = await adapi_client.get_user_group_ids(user_id)
    if not user_group_ids:
        return set()

    permissions: set[Permission] = set()
    for grant in grants:
        if grant.group_id in user_group_ids:
            permissions |= get_role_permissions(Role(grant.role))
    return permissions


async def _resolve_project_permissions(project: Project, user_id: str) -> set[Permission]:
    if project.user_id == user_id:
        return get_owner_permissions()

    permissions: set[Permission] = set()
    if is_admin(user_id):
        permissions |= get_admin_permissions()

    member = await get_project_member(project.id, user_id)
    if member is not None:
        permissions |= get_role_permissions(Role(member.role))

    permissions |= await resolve_group_permissions(project.id, user_id)
    return permissions


# Per-request cache: get_project and the permission dependencies both resolve the
# same (project, user) set, so resolving once avoids a second member lookup and
# ADAPI round-trip. ContextVars are per-task, so this never leaks across requests;
# the key guards against reuse for a different project/user in the same task.
_perm_cache: ContextVar[tuple[tuple[str, str], set[Permission]] | None] = ContextVar("_perm_cache", default=None)


async def resolve_project_permissions(project: Project, user_id: str) -> set[Permission]:
    cached = _perm_cache.get()
    if cached is not None and cached[0] == (project.id, user_id):
        return cached[1]
    permissions = await _resolve_project_permissions(project, user_id)
    _perm_cache.set(((project.id, user_id), permissions))
    return permissions


async def get_project(project_id: str, user_id: UserDep) -> Project:
    project = await db_get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not await resolve_project_permissions(project, user_id):
        raise HTTPException(status_code=404, detail="Project not found")

    _log_project_id.set(project.id)
    return project


ProjectDep = Annotated[Project, Depends(get_project)]


async def get_user_permissions(project: ProjectDep, user_id: UserDep) -> set[Permission]:
    permissions = await resolve_project_permissions(project, user_id)
    if not permissions:
        raise HTTPException(status_code=404, detail="Project not found")
    return permissions


PermissionsDep = Annotated[set[Permission], Depends(get_user_permissions)]


def require_permission(permission: Permission) -> Any:
    async def _check(user_permissions: PermissionsDep) -> set[Permission]:
        if not has_permission(user_permissions, permission):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user_permissions

    return Depends(_check)


async def _is_platform_group_member(user_id: str) -> bool:
    # Fetch the (small) set of granted group DNs and intersect in memory against
    # the user's ADAPI groups, rather than pushing the user's groups into a DB
    # query: a user can be in hundreds of groups, so that would be heavier. Revisit
    # only if the number of *granted* groups grows large.
    group_ids = await platform_group_ids()
    if not group_ids:
        return False
    user_group_ids = await adapi_client.get_user_group_ids(user_id)
    return bool(user_group_ids & group_ids)


async def has_platform_access(user_id: str) -> bool:
    if is_admin(user_id) or await db_is_platform_user(user_id):
        return True
    return await _is_platform_group_member(user_id)


async def require_platform_user(user_id: UserDep) -> str:
    if await has_platform_access(user_id):
        return user_id
    raise HTTPException(status_code=403, detail="Platform access required")


PlatformUserDep = Annotated[str, Depends(require_platform_user)]


# --- WebSocket variants ---


async def validate_ws_token(token: TokenDep) -> TokenPayload:
    """WS variant of validate_token: rejects the handshake instead of HTTP 401."""
    try:
        return validate_token(token)
    except HTTPException:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from None


async def get_ws_user_id(
    flow44_token: Annotated[str | None, Cookie(alias=settings.AUTH_COOKIE_NAME)] = None,
) -> str:
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


async def get_ws_permissions(project: WsProjectDep, user_id: WsUserDep) -> set[Permission]:
    permissions = await resolve_project_permissions(project, user_id)
    if not permissions:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return permissions


WsPermissionsDep = Annotated[set[Permission], Depends(get_ws_permissions)]


def require_ws_permission(permission: Permission) -> Any:
    async def _check(user_permissions: WsPermissionsDep) -> set[Permission]:
        if not has_permission(user_permissions, permission):
            raise WebSocketException(code=4403, reason="Insufficient permissions")
        return user_permissions

    return Depends(_check)


# --- Sandbox dependencies ---


async def get_sandbox(project: ProjectDep) -> PnpmSandbox:
    try:
        return await sandbox_manager.get_sandbox(project.id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project.id}") from exc


SandboxDep = Annotated[PnpmSandbox, Depends(get_sandbox)]


async def get_ws_sandbox(project: WsProjectDep) -> PnpmSandbox:
    try:
        return await sandbox_manager.get_sandbox(project.id)
    except Exception:
        logger.exception("Failed to get sandbox for project %s", project.id)
        raise WebSocketException(code=4404, reason="Sandbox not found") from None


WsSandboxDep = Annotated[PnpmSandbox, Depends(get_ws_sandbox)]
