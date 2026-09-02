from fastapi import APIRouter, HTTPException, Query

from flow44.api.deps import UserDep
from flow44.integrations.directory.client import AdGroup, AdUser, DirectoryError, directory_client

router = APIRouter(prefix="/api/directory", tags=["directory"])


@router.get("/users")
async def search_users(
    _user_id: UserDep,
    q: str = Query("", description="Substring matched against sAMAccountName, displayName or mail."),
) -> list[AdUser]:
    try:
        return await directory_client.search_users(q)
    except DirectoryError as exc:
        raise HTTPException(status_code=502, detail="Directory service unavailable") from exc


@router.get("/groups")
async def search_groups(
    _user_id: UserDep,
    q: str = Query("", description="Substring matched against sAMAccountName, displayName or mail."),
) -> list[AdGroup]:
    try:
        return await directory_client.search_groups(q)
    except DirectoryError as exc:
        raise HTTPException(status_code=502, detail="Directory service unavailable") from exc
