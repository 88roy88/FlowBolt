"""Thin client for ADAPI (Active Directory API).

Exposes what the backend needs from ADAPI: the set of groups a user belongs to
(for project-access resolution) and free-text search over users and groups (for
the "share a project with a person/group" UI).

Group membership is read from the user record's ``memberOf`` attribute, which
ADAPI returns as a list of group distinguished names (DNs). Those DNs are the
identifier the backend stores when a project or the platform is shared with a
group, so access resolution is a direct DN set-intersection — no objectGUID
mapping. ADAPI resolves nested (transitive) membership, so ``memberOf`` already
includes groups reached through nesting.

The two use cases differ in how they treat failure. Group-access resolution is
deliberately soft: if ADAPI is unreachable or errors, we log and return an empty
set, so group-derived access is simply unavailable for that request (direct
membership and ownership are unaffected). Interactive search instead raises
``AdapiError`` so the caller can surface "ADAPI unavailable" rather than
silently showing an empty result set that looks like "no matches".
"""

import logging
from urllib.parse import quote, urlencode

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
    # DNs of every group the user belongs to (transitive membership resolved by
    # ADAPI). Group grants key on these DNs, so this is what drives group-based
    # access resolution — see ``get_user_group_ids``.
    memberOf: list[str] = []  # noqa: N815 — mirrors the AD attribute name (wire contract)


class AdGroup(_AdRecord):
    description: str = ""
    # AD objectGUID — a stable directory id, kept for reference/display. The
    # grant key is the group's ``distinguishedName`` (on ``_AdRecord``), which is
    # what ADAPI reports in a user's ``memberOf``.
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
        """Return the DNs of every group ``user_id`` belongs to (transitive).

        ``user_id`` is the identifier carried in the auth token's UniqueID claim,
        which maps to the directory's ``sAMAccountName``. We look the user up via
        the same search ADAPI exposes and read the ``memberOf`` (group DNs) off
        the record whose ``sAMAccountName`` matches exactly — ADAPI carries the
        group DNs on the user object, so no separate membership endpoint is
        needed. Returns an empty set on any failure (unknown user, ADAPI down,
        malformed response) so group-derived access is unavailable, never fatal.
        """
        try:
            users = await self.search_users(user_id)
        except AdapiError as exc:
            logger.warning("ADAPI group lookup failed for user %s: %s", user_id, exc)
            return set()

        match = next((u for u in users if u.sAMAccountName.casefold() == user_id.casefold()), None)
        if match is None:
            logger.warning("ADAPI user not found for group lookup: %s", user_id)
            return set()
        return {dn for dn in match.memberOf if dn}

    async def search_users(self, query: str) -> list[AdUser]:
        """Search ADAPI for users matching ``query`` by account name, display name or email."""
        return [AdUser.model_validate(r) for r in await self._search("/users", query)]

    async def search_groups(self, query: str) -> list[AdGroup]:
        """Search ADAPI for groups matching ``query`` by account name, display name or email."""
        return [AdGroup.model_validate(r) for r in await self._search("/groups", query)]

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

        The query string is pre-encoded and appended to the URL rather than passed
        via ``params=``: httpx would encode the space inside ``customFilter`` as
        ``+``, which ADAPI reads literally and rejects. ``quote`` encodes it as
        ``%20`` instead, and httpx preserves an already-encoded query verbatim (no
        double-encoding).

        Raises ``AdapiError`` on any transport/HTTP/decoding failure or an
        unexpected (non-list) payload, so interactive callers can distinguish
        "ADAPI unavailable" from "no matches".
        """
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
