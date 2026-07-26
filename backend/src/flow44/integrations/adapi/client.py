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
        self,
        base_url: str | None = None,
        *,
        timeout_s: float | None = None,
        client_id: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ADAPI_BASE_URL).rstrip("/")
        self._timeout = timeout_s if timeout_s is not None else settings.ADAPI_TIMEOUT_SECONDS
        self._headers = {"ClientId": client_id if client_id is not None else settings.ADAPI_CLIENT_ID}

    async def get_user_group_ids(self, user_id: str) -> set[str]:
        try:
            users = await self._search_users({"customFilter": f"(mail={user_id})"})
        except AdapiError as exc:
            logger.warning("ADAPI group lookup failed for user %s: %s", user_id, exc)
            return set()

        match = next((u for u in users if u.mail.casefold() == user_id.casefold()), None)
        if match is None:
            logger.warning("ADAPI user not found for group lookup: %s", user_id)
            return set()
        return {dn for dn in match.member_of if dn}

    async def search_users(self, account_or_email_or_name: str) -> list[AdUser]:
        return await self._search_users(self._fuzzy_params(accountOrEmailOrName))

    async def _search_users(self, params: dict[str, str]) -> list[AdUser]:
        return [AdUser.model_validate(r) for r in await self._search("/users", params)]

    async def search_groups(self, query: str) -> list[AdGroup]:
        return [AdGroup.model_validate(r) for r in await self._search("/groups", self._fuzzy_params(query))]

    @staticmethod
    def _fuzzy_params(query: str) -> dict[str, str]:
        wrapped = f"*{query}*"
        return {
            "samAccountName": wrapped,
            "customFilter": f"(|(displayName={wrapped}) (mail={wrapped}))",
        }

    async def _search(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        # Params are pre-encoded and appended to the URL rather than passed via
        # params=: httpx encodes the space inside customFilter as "+", which ADAPI
        # rejects. quote encodes it as "%20", which httpx preserves verbatim.
        query_string = urlencode(params, quote_via=quote)
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                verify=settings.ADAPI_VERIFY_SSL,
                headers=self._headers,
            ) as http:
                resp = await http.get(f"{path}?{query_string}")
            # ADAPI answers a query that matches nothing with 404 rather than an
            # empty list. That's "no results", not a failure — return [] so the
            # UI shows "no results" instead of a directory-unavailable error.
            # Genuine faults (timeouts, connect errors, 5xx) still raise below.
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ADAPI search failed for %s params=%r: %s", path, params, exc)
            raise AdapiError(str(exc)) from exc
        if not isinstance(data, list):
            logger.warning("ADAPI returned a non-list payload for %s", path)
            raise AdapiError("ADAPI returned an unexpected payload")
        return [r for r in data if isinstance(r, dict)]


adapi_client = AdapiClient()
