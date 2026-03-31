from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Header, WebSocket

from flow44.config import settings
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import SandboxNotFoundError, sandbox_manager


def get_sandbox(project_id: str) -> PnpmSandbox:
    """HTTP dependency: resolves sandbox from path param, raises 404 if not found."""
    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project_id}") from None


async def get_ws_sandbox(websocket: WebSocket, project_id: str) -> PnpmSandbox | None:
    """WebSocket helper: returns sandbox or closes socket with 1008 and returns None."""
    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        await websocket.close(code=1008, reason="No sandbox")
        return None


SandboxDep = Depends(get_sandbox)


def get_authorization(authorization: str | None = Header(None, alias="Authorization")) -> str:
    """Require and validate Authorization header.

    The frontend sends SSO token (JWT or opaque) via Authorization header.
    - If JWT: validates structure, expiry, and optionally signature
    - If opaque: passes through (FLAPI will validate)
    """
    if not authorization or not authorization.strip():
        raise HTTPException(status_code=401, detail="Authorization required")

    token = authorization.strip()

    # Check if token looks like JWT (3 parts: header.payload.signature)
    is_jwt = token.count(".") == 2

    if is_jwt:
        try:
            # Decode JWT to check structure and expiry
            options = {"verify_signature": False}

            # If secret is configured, verify signature
            if settings.AUTH_JWT_SECRET:
                options["verify_signature"] = True
                payload = jwt.decode(
                    token,
                    settings.AUTH_JWT_SECRET,
                    algorithms=[settings.AUTH_JWT_ALGORITHM],
                )
            else:
                # No secret - just validate structure and expiry
                payload = jwt.decode(token, options=options)

            # PyJWT automatically checks 'exp' claim if verify_signature=True
            # For unverified tokens, manually check expiry
            if not settings.AUTH_JWT_SECRET and "exp" in payload:
                import time

                if payload["exp"] < time.time():
                    raise HTTPException(status_code=401, detail="Token expired")

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired") from None
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from None

    elif settings.AUTH_REQUIRE_JWT:
        # Configured to require JWT but token isn't JWT format
        raise HTTPException(status_code=401, detail="JWT token required")

    return token


# Type alias for auth dependency
AuthDep = Annotated[str, Depends(get_authorization)]
