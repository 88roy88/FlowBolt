"""ADAPI (Active Directory) search, proxied through the backend.

The browser must not call ADAPI directly: in production ADAPI lives at an
internal ``ADAPI_BASE_URL`` that isn't reachable from the browser and won't send
CORS headers. Routing search through the backend keeps it a server-to-server
call (no CORS), enforces auth, and gives us a single place to configure the
ADAPI endpoint.

Search is available to any authenticated user — it is how someone picks a person
or group to share a project with; it grants no access on its own.
"""

from fastapi import APIRouter, HTTPException, Query

from flow44.api.deps import UserDep
from flow44.integrations.adapi.client import AdapiError, AdGroup, AdUser, adapi_client

router = APIRouter(prefix="/api/adapi", tags=["adapi"])


@router.get("/users")
async def search_users(
    _user_id: UserDep,
    q: str = Query("", description="Substring matched against sAMAccountName, displayName or mail."),
) -> list[AdUser]:
    try:
        return await adapi_client.search_users(q)
    except AdapiError as exc:
        raise HTTPException(status_code=502, detail="ADAPI service unavailable") from exc


@router.get("/groups")
async def search_groups(
    _user_id: UserDep,
    q: str = Query("", description="Substring matched against sAMAccountName, displayName or mail."),
) -> list[AdGroup]:
    try:
        return await adapi_client.search_groups(q)
    except AdapiError as exc:
        raise HTTPException(status_code=502, detail="ADAPI service unavailable") from exc
