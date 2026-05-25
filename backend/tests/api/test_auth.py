"""Tests for extract_user_id behavior (unsigned JWT payload parsing).

Covers the behavior matrix in auth.py:
- No token + AUTH_REQUIRE_JWT on/off
- JWT-shaped + URL ``/UniqueID`` claim present / missing / undecodable
- JWT-shaped + AUTH_REQUIRE_JWT on/off (strict vs dev fallback)
- Opaque token + AUTH_REQUIRE_JWT on/off
"""

import time
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from flow44.api.auth import extract_user_id

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


@patch("flow44.api.auth.settings")
def test_no_token_require_jwt_raises(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    with pytest.raises(HTTPException) as exc:
        extract_user_id(None)
    assert exc.value.status_code == 401


@patch("flow44.api.auth.settings")
def test_no_token_no_require_returns_anonymous(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    assert extract_user_id(None) == "anonymous"


# ---------------------------------------------------------------------------
# JWT-shaped: URL /UniqueID claim
# ---------------------------------------------------------------------------


@patch("flow44.api.auth.settings")
def test_jwt_url_unique_id_claim_returned(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt({CLAIM_UNIQUE_ID_URL: "user-123"})
    assert extract_user_id(token) == "user-123"


@patch("flow44.api.auth.settings")
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
    assert extract_user_id(token) == "first"


@patch("flow44.api.auth.settings")
def test_jwt_missing_unique_id_claim_raises_when_required(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    token = _make_jwt({"sub": "ignored", "role": "admin"})
    with pytest.raises(HTTPException) as exc:
        extract_user_id(token)
    assert exc.value.status_code == 401
    assert "missing user identification" in exc.value.detail.lower()


@patch("flow44.api.auth.settings")
def test_jwt_expired_still_extracts_when_exp_verification_disabled(mock_settings):
    """Decode skips exp check; claim still readable on signed-but-expired token."""
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt(
        {
            CLAIM_UNIQUE_ID_URL: "user-x",
            "exp": int(time.time()) - 10,
        }
    )
    assert extract_user_id(token) == "user-x"


@patch("flow44.api.auth.settings")
def test_jwt_malformed_raises_when_required(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    # Exactly two dots; payload segment decodes to non-JSON bytes.
    bad = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YWFh.YWFh"
    with pytest.raises(HTTPException) as exc:
        extract_user_id(bad)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# JWT-shaped + AUTH_REQUIRE_JWT=false (dev permissive)
# ---------------------------------------------------------------------------


@patch("flow44.api.auth.settings")
def test_jwt_no_unique_id_no_require_returns_raw_token(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    token = _make_jwt({"sub": "user-local"})
    result = extract_user_id(token)
    assert result == token
    assert result != "user-local"


@patch("flow44.api.auth.settings")
def test_jwt_valid_claim_no_require_returns_uid(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    token = _make_jwt({CLAIM_UNIQUE_ID_URL: "dev-user"})
    assert extract_user_id(token) == "dev-user"


@patch("flow44.api.auth.settings")
def test_jwt_malformed_no_require_returns_raw_string(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    raw = "x.y.z"
    assert extract_user_id(raw) == raw


@patch("flow44.api.auth.settings")
def test_jwt_require_true_accepts_unsigned_payload_with_claim(mock_settings):
    """Signed HS256 token with claim returns uid under strict mode."""
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_PUBLIC_KEY = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    forged = _make_jwt({CLAIM_UNIQUE_ID_URL: "parsed-user"})
    assert _jwt_shaped(forged)
    assert extract_user_id(forged) == "parsed-user"


# ---------------------------------------------------------------------------
# Opaque token cases
# ---------------------------------------------------------------------------


@patch("flow44.api.auth.settings")
def test_opaque_token_require_jwt_raises(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    with pytest.raises(HTTPException) as exc:
        extract_user_id("some-opaque-api-key")
    assert exc.value.status_code == 401
    assert "JWT" in exc.value.detail


@patch("flow44.api.auth.settings")
def test_opaque_token_no_require_returns_as_user_id(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    assert extract_user_id("my-opaque-key") == "my-opaque-key"
