from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Query, Request, Response, WebSocket

from flow44.config import settings
from flow44.db.project import Project
from flow44.db.project import get_project as db_get_project

logger = logging.getLogger(__name__)


def get_authorization_header(
    authorization: str | None = Header(None, alias="Authorization"),
    token: str | None = Query(None),
    fb_token: str | None = Cookie(None),
) -> str | None:
    raw = (authorization or token or fb_token or "").strip()
    if not raw:
        return None
    return raw[7:].strip() if raw.lower().startswith("bearer ") else raw


TokenDep = Annotated[str | None, Depends(get_authorization_header)]


def extract_user_id(token: str | None) -> str:
    """Resolve a raw token string to a user_id.

    Behavior matrix:
    - No token + AUTH_REQUIRE_JWT=true  -> 401
    - No token + AUTH_REQUIRE_JWT=false -> "anonymous"
    - JWT-shaped + AUTH_JWT_SECRET set  -> verify signature, extract sub/UniqueID/id
    - JWT-shaped + no secret + AUTH_REQUIRE_JWT=true  -> 401 (config error; forged tokens rejected)
    - JWT-shaped + no secret + AUTH_REQUIRE_JWT=false -> treat as opaque (dev mode, no decode)
    - Opaque   + AUTH_REQUIRE_JWT=true  -> 401
    - Opaque   + AUTH_REQUIRE_JWT=false -> token value used as user_id
    """
    if not token:
        if settings.AUTH_REQUIRE_JWT:
            raise HTTPException(status_code=401, detail="Authorization required")
        return "anonymous"

    is_jwt = token.count(".") == 2

    if is_jwt:
        if not settings.AUTH_JWT_SECRET:
            if settings.AUTH_REQUIRE_JWT:
                # Cannot verify signature — reject to prevent forged-token impersonation.
                logger.warning(
                    "JWT token received but AUTH_JWT_SECRET is not configured; "
                    "rejecting request to prevent forged-token impersonation. "
                    "Set AUTH_JWT_SECRET or disable AUTH_REQUIRE_JWT for local dev."
                )
                raise HTTPException(status_code=401, detail="Server authentication is misconfigured")
            # AUTH_REQUIRE_JWT=false + no secret: treat whole token as opaque user_id (local dev only).
            return token

        try:
            payload = jwt.decode(
                token,
                settings.AUTH_JWT_SECRET,
                algorithms=[settings.AUTH_JWT_ALGORITHM],
            )
            uid = payload.get("UniqueID") or payload.get("sub") or payload.get("id")
            if not uid:
                raise HTTPException(status_code=401, detail="Token missing user identification")
            return str(uid)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired") from None
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from None

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
    """WS auth via query param token; delegates ownership check to get_project."""
    token = websocket.query_params.get("token") or websocket.cookies.get("fb_token")
    try:
        user_id = extract_user_id(token)
        return await get_project(project_id, user_id)
    except HTTPException:
        await websocket.close(code=1008, reason="Unauthorized")
        return None


async def preview_token_cookie(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Promote ?token= to an httponly cookie scoped to the preview proxy path.

    Set once on the first authenticated preview hit so subsequent sub-resource
    requests (assets, Vite HMR socket) can authenticate via cookie without
    needing the token in every query string.
    """
    response = await call_next(request)
    token = request.query_params.get("token")
    if token:
        parts = request.url.path.split("/")
        # /api/preview/{project_id}/proxy/...  →  parts[3] is project_id
        if len(parts) >= 5 and parts[1] == "api" and parts[2] == "preview" and parts[4] == "proxy":
            response.set_cookie(
                key="fb_token",
                value=token,
                path=f"/api/preview/{parts[3]}/proxy",
                httponly=True,
                samesite="lax",
            )
    return response
