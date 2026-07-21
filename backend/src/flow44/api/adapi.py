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
