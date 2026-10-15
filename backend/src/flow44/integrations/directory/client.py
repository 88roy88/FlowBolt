import logging
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, computed_field

from flow44.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "AdGroup",
    "AdUser",
    "DirectoryClient",
    "DirectoryError",
    "directory_client",
    "domain_from_user",
    "unique_id_from_user",
]


class DirectoryError(Exception):
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

    @computed_field(alias="uniqueId")  # type: ignore[prop-decorator]
    @property
    def unique_id(self) -> str:
        return unique_id_from_user(self)


def domain_from_user(user: AdUser) -> str:
    mail_domain = user.mail.partition("@")[2].casefold()
    domain_map = {k.casefold(): v for k, v in settings.DIRECTORY_MAIL_DOMAIN_MAP.items()}
    return domain_map.get(mail_domain, settings.DIRECTORY_DEFAULT_DOMAIN)


def unique_id_from_user(user: AdUser) -> str:
    domain = domain_from_user(user)
    if not user.sam_account_name or not domain:
        return ""
    return f"{user.sam_account_name}@{domain}"


def _escape_filter_value(value: str) -> str:
    """Escape LDAP filter metacharacters (RFC 4515) so a search term can't alter the filter."""
    return "".join(f"\\{ord(c):02x}" if c in "\\*()\0" else c for c in value)


class AdGroup(_AdRecord):
    description: str = ""
    object_guid: str = Field(default="", alias="objectGUID")


class DirectoryClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_s: float | None = None,
        client_id: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.DIRECTORY_BASE_URL).rstrip("/")
        self._timeout = timeout_s if timeout_s is not None else settings.DIRECTORY_TIMEOUT_SECONDS
        self._headers = {"ClientId": client_id if client_id is not None else settings.DIRECTORY_CLIENT_ID}

    async def get_user_group_ids(self, user_id: str) -> set[str]:
        sam_account_name = user_id.partition("@")[0]
        try:
            users = await self._search_users({"customFilter": f"(sAMAccountName={sam_account_name})"})
        except DirectoryError as exc:
            logger.warning("Directory group lookup failed for user %s: %s", user_id, exc)
            return set()

        match = next((u for u in users if u.unique_id.casefold() == user_id.casefold()), None)
        if match is None:
            logger.warning("Directory user not found for group lookup: %s", user_id)
            return set()
        return {dn for dn in match.member_of if dn}

    async def search_users(self, query: str) -> list[AdUser]:
        return await self._search_users({"aNR": query})

    async def _search_users(self, params: dict[str, str]) -> list[AdUser]:
        return [AdUser.model_validate(r) for r in await self._search("/users", params)]

    async def search_groups(self, query: str) -> list[AdGroup]:
        wrapped = f"*{_escape_filter_value(query)}*"
        # groupType <= 0 keeps security groups and drops distribution lists.
        custom_filter = f"(&(|(displayName={wrapped})(samAccountName={wrapped}))(groupType<=0))"
        return [AdGroup.model_validate(r) for r in await self._search("/groups", {"customFilter": custom_filter})]

    async def _search(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        # Encode spaces as %20, not httpx's "+", which the directory service rejects.
        query_string = urlencode(params, quote_via=quote)
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                verify=settings.DIRECTORY_VERIFY_SSL,
                headers=self._headers,
            ) as http:
                resp = await http.get(f"{path}?{query_string}")
            if resp.status_code == 404:
                # The directory service returns 404 on "no results"
                return []
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Directory search failed for %s params=%r: %s", path, params, exc)
            raise DirectoryError(str(exc)) from exc
        if not isinstance(data, list):
            logger.warning("Directory service returned a non-list payload for %s", path)
            raise DirectoryError("Directory service returned an unexpected payload")
        return [r for r in data if isinstance(r, dict)]


directory_client = DirectoryClient()
