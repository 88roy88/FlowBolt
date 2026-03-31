import time
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, WebSocket

from flow44.config import settings
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import SandboxNotFoundError, sandbox_manager


def get_sandbox(project_id: str) -> PnpmSandbox:
    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project_id}") from None


async def get_ws_sandbox(websocket: WebSocket, project_id: str) -> PnpmSandbox | None:
    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        await websocket.close(code=1008, reason="No sandbox")
        return None


SandboxDep = Depends(get_sandbox)


def get_authorization(authorization: str | None = Header(None, alias="Authorization")) -> str:
    if not authorization or not authorization.strip():
        raise HTTPException(status_code=401, detail="Authorization required")

    token = authorization.strip()
    is_jwt = token.count(".") == 2

    if is_jwt:
        try:
            if settings.AUTH_JWT_SECRET:
                payload = jwt.decode(
                    token,
                    settings.AUTH_JWT_SECRET,
                    algorithms=[settings.AUTH_JWT_ALGORITHM],
                )
            else:
                payload = jwt.decode(token, options={"verify_signature": False})

            if not settings.AUTH_JWT_SECRET and "exp" in payload and payload["exp"] < time.time():
                raise HTTPException(status_code=401, detail="Token expired")

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired") from None
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from None

    elif settings.AUTH_REQUIRE_JWT:
        raise HTTPException(status_code=401, detail="JWT token required")

    return token


AuthDep = Annotated[str, Depends(get_authorization)]
