import logging
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field

from flow44.config import settings

logger = logging.getLogger(__name__)

__all__ = ["AdGroup", "AdUser", "AdapiClient", "AdapiError", "adapi_client"]


class AdapiError(Exception):
    pass


class _AdRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    cn: str
    display_name: str = Field(default="", alias="displayName")
    distinguished_name: str = Field(default="", alias="distinguishedName")
    mail: str = ""
    sam_account_name: str = Field(default="", alias="sAMAccountName")


class AdUser(_AdRecord):
    member_of: list[str] = Field(default=[], alias="memberOf")


class AdGroup(_AdRecord):
    description: str = ""
    object_guid: str = Field(default="", alias="objectGUID")


class AdapiClient:
    def __init__(
        self, base_url: str | None = None, *, timeout_s: float | None = None, client_id: str | None = None
    ) -> None:
        self.base_url = (base_url or settings.ADAPI_BASE_URL).rstrip("/")
        self._timeout = timeout_s if timeout_s is not None else settings.ADAPI_TIMEOUT_SECONDS
        self._headers = {"ClientId": client_id if client_id is not None else settings.ADAPI_CLIENT_ID}

    async def get_user_group_ids(self, user_id: str) -> set[str]:
        # user_id is the caller's email (our user id), matched against ADAPI's mail.
        try:
            users = await self.search_users(user_id)
        except AdapiError as exc:
            logger.warning("ADAPI group lookup failed for user %s: %s", user_id, exc)
            return set()

        match = next((u for u in users if u.mail.casefold() == user_id.casefold()), None)
        if match is None:
            logger.warning("ADAPI user not found for group lookup: %s", user_id)
            return set()
        return {dn for dn in match.member_of if dn}

    async def search_users(self, query: str) -> list[AdUser]:
        return [AdUser.model_validate(r) for r in await self._search("/users", query)]

    async def search_groups(self, query: str) -> list[AdGroup]:
        return [AdGroup.model_validate(r) for r in await self._search("/groups", query)]

    @staticmethod
    def _search_params(query: str) -> dict[str, str]:
        wrapped = f"*{query}*"
        return {
            "samAccountName": wrapped,
            "customFilter": f"(|(displayName={wrapped}) (mail={wrapped}))",
        }

    async def _search(self, path: str, query: str) -> list[dict[str, Any]]:
        # The query is pre-encoded and appended to the URL rather than passed via
        # params=: httpx encodes the space inside customFilter as "+", which ADAPI
        # rejects. quote encodes it as "%20", which httpx preserves verbatim.
        query_string = urlencode(self._search_params(query), quote_via=quote)
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                verify=settings.ADAPI_VERIFY_SSL,
                headers=self._headers,
            ) as http:
                resp = await http.get(f"{path}?{query_string}")
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ADAPI search failed for %s query=%r: %s", path, query, exc)
            raise AdapiError(str(exc)) from exc
        if not isinstance(data, list):
            logger.warning("ADAPI returned a non-list payload for %s", path)
            raise AdapiError("ADAPI returned an unexpected payload")
        return [r for r in data if isinstance(r, dict)]


adapi_client = AdapiClient()
