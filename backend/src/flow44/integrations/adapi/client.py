"""Thin client for ADAPI (Active Directory API).

Exposes what the backend needs from ADAPI: the set of groups a user belongs to
(for project-access resolution) and free-text search over users and groups (for
the "share a project with a person/group" UI). Nested (transitive) membership is
resolved by ADAPI itself, so the backend never has to deal with DNs or
``memberOf`` chains.

The two use cases differ in how they treat failure. Group-access resolution is
deliberately soft: if ADAPI is unreachable or errors, we log and return an empty
set, so group-derived access is simply unavailable for that request (direct
membership and ownership are unaffected). Interactive search instead raises
``AdapiError`` so the caller can surface "ADAPI unavailable" rather than
silently showing an empty result set that looks like "no matches".
"""

import logging
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict

from flow44.config import settings

logger = logging.getLogger(__name__)

__all__ = ["AdGroup", "AdUser", "AdapiClient", "AdapiError", "adapi_client"]


class AdapiError(Exception):
    """Raised when an ADAPI search cannot be completed (ADAPI down or malformed)."""


class _AdRecord(BaseModel):
    # ADAPI carries more fields than we model; ignore the rest rather than
    # reject the record. Field names mirror the AD attribute names.
    model_config = ConfigDict(extra="ignore")

    cn: str
    displayName: str = ""  # noqa: N815 — mirrors the AD attribute name (wire contract)
    distinguishedName: str = ""  # noqa: N815
    mail: str = ""
    sAMAccountName: str = ""  # noqa: N815


class AdUser(_AdRecord):
    pass


class AdGroup(_AdRecord):
    description: str = ""
    # Stable directory identifier. Needed to grant a group access to a project
    # (project_member_groups keys on it), so it must survive the wire, unlike the
    # display-only fields above.
    objectGUID: str = ""  # noqa: N815 — mirrors the AD attribute name (wire contract)


class AdapiClient:
    def __init__(
        self, base_url: str | None = None, *, timeout_s: float | None = None, client_id: str | None = None
    ) -> None:
        self.base_url = (base_url or settings.ADAPI_BASE_URL).rstrip("/")
        self._timeout = timeout_s if timeout_s is not None else settings.ADAPI_TIMEOUT_SECONDS
        # Sent as the ``ClientId`` header so ADAPI can attribute the call.
        self._headers = {"ClientId": client_id if client_id is not None else settings.ADAPI_CLIENT_ID}

    async def get_user_group_ids(self, user_id: str) -> set[str]:
        """Return the ``objectGUID``s of every group ``user_id`` belongs to (transitive).

        ``user_id`` is the identifier carried in the auth token's UniqueID claim,
        which maps to the directory's ``sAMAccountName``. Returns an empty set on
        any failure (unknown user, ADAPI down, malformed response).
        """
        path = f"/api/users/{quote(user_id, safe='')}/groups"
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                verify=settings.ADAPI_VERIFY_SSL,
                headers=self._headers,
            ) as http:
                resp = await http.get(path)
            if resp.status_code == 404:
                logger.warning("ADAPI user not found: %s (404)", user_id)
                return set()
            resp.raise_for_status()
            groups = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ADAPI group lookup failed for user %s: %s", user_id, exc)
            return set()

        if not isinstance(groups, list):
            logger.warning("ADAPI returned unexpected payload for user %s groups", user_id)
            return set()
        return {g["objectGUID"] for g in groups if isinstance(g, dict) and g.get("objectGUID")}

    async def search_users(self, query: str) -> list[AdUser]:
        """Search ADAPI for users matching ``query`` by account name, display name or email."""
        return [AdUser.model_validate(r) for r in await self._search("/api/users", query)]

    async def search_groups(self, query: str) -> list[AdGroup]:
        """Search ADAPI for groups matching ``query`` by account name, display name or email."""
        return [AdGroup.model_validate(r) for r in await self._search("/api/groups", query)]

    @staticmethod
    def _search_params(query: str) -> dict[str, str]:
        """Build the ADAPI search filter for ``query``.

        Matches the term as a substring against ``sAMAccountName``, ``displayName``
        or ``mail`` (ADAPI ORs ``samAccountName`` with ``customFilter``). The term
        is wrapped in ``*…*`` LDAP wildcards so it matches anywhere in the value.
        """
        wrapped = f"*{query}*"
        return {
            "samAccountName": wrapped,
            "customFilter": f"(|(displayName={wrapped}) (mail={wrapped}))",
        }

    async def _search(self, path: str, query: str) -> list[dict]:
        """GET ``path`` with the substring filter and return the raw list of records.

        Raises ``AdapiError`` on any transport/HTTP/decoding failure or an
        unexpected (non-list) payload, so interactive callers can distinguish
        "ADAPI unavailable" from "no matches".
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                verify=settings.ADAPI_VERIFY_SSL,
                headers=self._headers,
            ) as http:
                resp = await http.get(path, params=self._search_params(query))
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
