"""Tests for get_user_id behavior, decode_token, and TokenPayload parsing.

Covers the behavior matrix in auth.py:
- No token + AUTH_REQUIRE_JWT on/off
- JWT-shaped + URL ``/UniqueID`` claim present / missing / undecodable
- JWT-shaped + AUTH_REQUIRE_JWT on/off (strict vs dev fallback)
- Opaque token + AUTH_REQUIRE_JWT on/off
- TokenPayload lifts URL-suffixed claims and preserves extras
"""

import time
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from flow44.api.deps import TokenPayload, decode_token, get_user_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECRET = "x" * 32  # noqa: S105 — test-only HS256 key
ALGORITHM = "HS256"

# Claim key must end with ``/UniqueID`` (case-sensitive).
CLAIM_UNIQUE_ID_URL = "https://issuer.example/v1/claims/UniqueID"


def _make_jwt(payload: dict, secret: str = SECRET, algorithm: str = ALGORITHM) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def _jwt_shaped(raw: str) -> bool:
    return raw.count(".") == 2


# ---------------------------------------------------------------------------
# No-token cases
# ---------------------------------------------------------------------------


@patch("flow44.api.deps.settings")
def test_no_token_require_jwt_raises(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    with pytest.raises(HTTPException) as exc:
        get_user_id(None)
    assert exc.value.status_code == 401


@patch("flow44.api.deps.settings")
def test_no_token_no_require_returns_611noat(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    assert get_user_id(None) == "611noat"


# ---------------------------------------------------------------------------
# JWT-shaped: URL /UniqueID claim
# ---------------------------------------------------------------------------


@patch("flow44.api.deps.settings")
def test_jwt_url_unique_id_claim_returned(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt({CLAIM_UNIQUE_ID_URL: "user-123"})
    assert get_user_id(token) == "user-123"


@patch("flow44.api.deps.settings")
def test_jwt_first_matching_url_claim_wins(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt(
        {
            "https://other.example/claims/UniqueID": "first",
            CLAIM_UNIQUE_ID_URL: "second",
        }
    )
    assert get_user_id(token) == "first"


@patch("flow44.api.deps.settings")
def test_jwt_missing_unique_id_claim_raises_when_required(mock_settings):
    """Validly signed token that decodes but lacks a UniqueID claim."""
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt({"sub": "ignored", "role": "admin"})
    with pytest.raises(HTTPException) as exc:
        get_user_id(token)
    assert exc.value.status_code == 401
    assert "missing user identification" in exc.value.detail.lower()


@patch("flow44.api.deps.settings")
def test_jwt_expired_rejected_when_required(mock_settings):
    """Expired token fails decode (exp verified), so strict mode rejects it with 401."""
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt(
        {
            CLAIM_UNIQUE_ID_URL: "user-x",
            "exp": int(time.time()) - 10,
        }
    )
    with pytest.raises(HTTPException) as exc:
        get_user_id(token)
    assert exc.value.status_code == 401
    assert "invalid or expired" in exc.value.detail.lower()


@patch("flow44.api.deps.settings")
def test_jwt_unexpired_accepted(mock_settings):
    """A token whose exp is still in the future decodes and yields the uid."""
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt(
        {
            CLAIM_UNIQUE_ID_URL: "user-y",
            "exp": int(time.time()) + 3600,
        }
    )
    assert get_user_id(token) == "user-y"


@patch("flow44.api.deps.settings")
def test_jwt_malformed_raises_when_required(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    # Exactly two dots; payload segment decodes to non-JSON bytes.
    bad = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YWFh.YWFh"
    with pytest.raises(HTTPException) as exc:
        get_user_id(bad)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# JWT-shaped + AUTH_REQUIRE_JWT=false (dev permissive)
# ---------------------------------------------------------------------------


@patch("flow44.api.deps.settings")
def test_jwt_no_unique_id_no_require_returns_raw_token(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    token = _make_jwt({"sub": "user-local"})
    result = get_user_id(token)
    assert result == token
    assert result != "user-local"


@patch("flow44.api.deps.settings")
def test_jwt_valid_claim_no_require_returns_uid(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt({CLAIM_UNIQUE_ID_URL: "dev-user"})
    assert get_user_id(token) == "dev-user"


@patch("flow44.api.deps.settings")
def test_jwt_malformed_no_require_returns_raw_string(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    raw = "x.y.z"
    assert get_user_id(raw) == raw


@patch("flow44.api.deps.settings")
def test_jwt_require_true_accepts_unsigned_payload_with_claim(mock_settings):
    """Signed HS256 token with claim returns uid under strict mode."""
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    forged = _make_jwt({CLAIM_UNIQUE_ID_URL: "parsed-user"})
    assert _jwt_shaped(forged)
    assert get_user_id(forged) == "parsed-user"


# ---------------------------------------------------------------------------
# Opaque token cases
# ---------------------------------------------------------------------------


@patch("flow44.api.deps.settings")
def test_opaque_token_require_jwt_raises(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    with pytest.raises(HTTPException) as exc:
        get_user_id("some-opaque-api-key")
    assert exc.value.status_code == 401
    assert "JWT" in exc.value.detail


@patch("flow44.api.deps.settings")
def test_opaque_token_no_require_returns_as_user_id(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    assert get_user_id("my-opaque-key") == "my-opaque-key"


# ---------------------------------------------------------------------------
# decode_token + TokenPayload
# ---------------------------------------------------------------------------


CLAIM_PREFIX = "https://issuer.example/v1/claims/"


@patch("flow44.api.deps.settings")
def test_decode_token_returns_payload_on_valid_jwt(mock_settings):
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt({CLAIM_UNIQUE_ID_URL: "u-1", "iss": "test-issuer"})
    payload = decode_token(token)
    assert isinstance(payload, TokenPayload)
    assert payload.unique_id == "u-1"
    assert payload.iss == "test-issuer"


@patch("flow44.api.deps.settings")
def test_decode_token_returns_none_on_garbage(mock_settings):
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    assert decode_token("not-a-jwt") is None
    assert decode_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YWFh.YWFh") is None


def test_token_payload_lifts_all_url_suffixed_claims():
    payload = TokenPayload.model_validate(
        {
            CLAIM_PREFIX + "UniqueID": "user-42",
            CLAIM_PREFIX + "givenname": "Ada",
            CLAIM_PREFIX + "surname": "Lovelace",
            "iss": "ex",
            "exp": 1700000000,
        }
    )
    assert payload.unique_id == "user-42"
    assert payload.given_name == "Ada"
    assert payload.surname == "Lovelace"
    assert payload.iss == "ex"
    assert payload.exp == 1700000000


def test_token_payload_preserves_unknown_claims_via_extra():
    payload = TokenPayload.model_validate(
        {CLAIM_PREFIX + "UniqueID": "u", "custom_role": "admin", "sub": "ignored-by-model"}
    )
    dumped = payload.model_dump()
    assert dumped["custom_role"] == "admin"
    assert dumped["sub"] == "ignored-by-model"


def test_token_payload_first_url_suffix_match_wins():
    payload = TokenPayload.model_validate(
        {
            "https://other.example/claims/UniqueID": "first",
            CLAIM_PREFIX + "UniqueID": "second",
        }
    )
    assert payload.unique_id == "first"
