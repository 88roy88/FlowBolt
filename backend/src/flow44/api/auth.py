from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, cast

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, WebSocket
from starlette.datastructures import MutableHeaders
from jwt.types import Options

from flow44.config import settings
from flow44.db.project import Project
from flow44.db.project import get_project as db_get_project

logger = logging.getLogger(__name__)

_DECODE_OPTIONS = {
    "verify_signature": False,
    "verify_exp": False,
    "verify_nbf": False,
    "verify_iat": False,
    "verify_aud": False,
}


def _find_unique_id(payload: dict[str, object]) -> str | None:
    return next((str(v) for k, v in payload.items() if k.endswith("/UniqueID")), None)


def get_authorization_header(
    authorization: str | None = Header(None, alias="Authorization"),
    fb_token: str | None = Cookie(None),
) -> str | None:
    raw = (authorization or fb_token or "").strip()
    if not raw:
        return None
    return raw[7:].strip() if raw.lower().startswith("bearer ") else raw


TokenDep = Annotated[str | None, Depends(get_authorization_header)]


def extract_user_id(token: str | None) -> str:
    """Resolve token to user_id. JWT payload parsed unsigned; uid from ``/UniqueID`` claim."""
    if not token:
        if settings.AUTH_REQUIRE_JWT:
            raise HTTPException(status_code=401, detail="Authorization required")
        return "anonymous"

    is_jwt = token.count(".") == 2

    if is_jwt:
        try:
            decoded = jwt.decode(
                token,
                "",
                algorithms=[settings.AUTH_JWT_ALGORITHM],
                options=cast(Options, _DECODE_OPTIONS),
            )
            uid = _find_unique_id(decoded) if isinstance(decoded, dict) else None
        except jwt.PyJWTError as e:
            logger.debug("JWT parse failed: %s", e)
            uid = None

        if uid:
            return uid

        if settings.AUTH_REQUIRE_JWT:
            raise HTTPException(status_code=401, detail="Token missing user identification")
        return token

    elif settings.AUTH_REQUIRE_JWT:
        raise HTTPException(status_code=401, detail="JWT token required")

    return token


def get_user_id(authorization: TokenDep) -> str:
    return extract_user_id(authorization)


UserDep = Annotated[str, Depends(get_user_id)]


async def get_project(project_id: str, user_id: UserDep) -> Project:
    project = await db_get_project(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


ProjectDep = Annotated[Project, Depends(get_project)]


async def get_ws_project(websocket: WebSocket, project_id: str) -> Project | None:
    """WS auth via query param or cookie."""
    token = websocket.query_params.get("token") or websocket.cookies.get("fb_token")
    try:
        user_id = extract_user_id(token)
        return await get_project(project_id, user_id)
    except HTTPException:
        await websocket.close(code=1008, reason="Unauthorized")
        return None


def _preview_project_id(path: str) -> str | None:
    # nginx guarantees /api/preview/{id}/proxy/... structure before routing here
    if not path.startswith("/api/preview/"):
        return None
    project_id, _, _ = path.removeprefix("/api/preview/").partition("/")
    return project_id or None


async def preview_token_cookie(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Scope ?token= to preview proxy: inject as fb_token cookie so sub-resources authenticate."""
    token = request.query_params.get("token")
    project_id = _preview_project_id(request.url.path) if token else None

    if not project_id:
        return await call_next(request)

    MutableHeaders(scope=request.scope)["authorization"] = f"Bearer {token}"

    response = await call_next(request)
    response.set_cookie("fb_token", token, path=f"/api/preview/{project_id}/proxy", httponly=True, samesite="lax")
    return response
