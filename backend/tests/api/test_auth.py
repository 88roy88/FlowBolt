"""Tests for extract_user_id JWT validation behavior.

Covers the full behavior matrix described in auth.py:
- No token  + AUTH_REQUIRE_JWT on/off
- JWT-shaped + secret set (valid / expired / missing claims)
- JWT-shaped + no secret  + AUTH_REQUIRE_JWT on/off  (the hardened paths)
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

SECRET = "test-secret"  # noqa: S105
ALGORITHM = "HS256"


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
    mock_settings.AUTH_JWT_SECRET = SECRET
    with pytest.raises(HTTPException) as exc:
        extract_user_id(None)
    assert exc.value.status_code == 401


@patch("flow44.api.auth.settings")
def test_no_token_no_require_returns_anonymous(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    mock_settings.AUTH_JWT_SECRET = None
    assert extract_user_id(None) == "anonymous"


# ---------------------------------------------------------------------------
# JWT-shaped token WITH a configured secret
# ---------------------------------------------------------------------------


@patch("flow44.api.auth.settings")
def test_jwt_sub_claim_returned(mock_settings):
    mock_settings.AUTH_JWT_SECRET = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    mock_settings.AUTH_REQUIRE_JWT = True
    token = _make_jwt({"sub": "user-123"})
    assert extract_user_id(token) == "user-123"


@patch("flow44.api.auth.settings")
def test_jwt_unique_id_claim_preferred(mock_settings):
    """UniqueID takes precedence over sub when both are present."""
    mock_settings.AUTH_JWT_SECRET = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    mock_settings.AUTH_REQUIRE_JWT = True
    token = _make_jwt({"UniqueID": "uid-abc", "sub": "sub-xyz"})
    assert extract_user_id(token) == "uid-abc"


@patch("flow44.api.auth.settings")
def test_jwt_id_claim_fallback(mock_settings):
    mock_settings.AUTH_JWT_SECRET = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    mock_settings.AUTH_REQUIRE_JWT = True
    token = _make_jwt({"id": "id-999"})
    assert extract_user_id(token) == "id-999"


@patch("flow44.api.auth.settings")
def test_jwt_missing_user_claims_raises(mock_settings):
    mock_settings.AUTH_JWT_SECRET = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    mock_settings.AUTH_REQUIRE_JWT = True
    token = _make_jwt({"role": "admin"})
    with pytest.raises(HTTPException) as exc:
        extract_user_id(token)
    assert exc.value.status_code == 401
    assert "missing user identification" in exc.value.detail


@patch("flow44.api.auth.settings")
def test_jwt_expired_raises(mock_settings):
    mock_settings.AUTH_JWT_SECRET = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    mock_settings.AUTH_REQUIRE_JWT = True
    token = _make_jwt({"sub": "user-x", "exp": int(time.time()) - 10})
    with pytest.raises(HTTPException) as exc:
        extract_user_id(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


@patch("flow44.api.auth.settings")
def test_jwt_wrong_secret_raises(mock_settings):
    mock_settings.AUTH_JWT_SECRET = SECRET
    mock_settings.AUTH_JWT_ALGORITHM = ALGORITHM
    mock_settings.AUTH_REQUIRE_JWT = True
    token = _make_jwt({"sub": "user-x"}, secret="wrong-secret")  # noqa: S106
    with pytest.raises(HTTPException) as exc:
        extract_user_id(token)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# JWT-shaped token WITHOUT a configured secret  (hardened behavior)
# ---------------------------------------------------------------------------


@patch("flow44.api.auth.settings")
def test_jwt_no_secret_require_jwt_raises(mock_settings):
    """When AUTH_REQUIRE_JWT=true and no secret, JWT MUST be rejected (prevents forgery)."""
    mock_settings.AUTH_JWT_SECRET = None
    mock_settings.AUTH_REQUIRE_JWT = True
    # Forge a JWT with arbitrary payload — should be rejected even though it looks valid
    forged = _make_jwt({"sub": "attacker", "UniqueID": "victim-user"})
    assert _jwt_shaped(forged), "test pre-condition: token must look JWT-shaped"
    with pytest.raises(HTTPException) as exc:
        extract_user_id(forged)
    assert exc.value.status_code == 401
    assert "misconfigured" in exc.value.detail.lower()


@patch("flow44.api.auth.settings")
def test_jwt_no_secret_no_require_returns_opaque(mock_settings):
    """When AUTH_REQUIRE_JWT=false and no secret, JWT is treated as opaque (local dev mode)."""
    mock_settings.AUTH_JWT_SECRET = None
    mock_settings.AUTH_REQUIRE_JWT = False
    token = _make_jwt({"sub": "user-local"})
    # Should not decode — must return the raw token string, not the sub claim
    result = extract_user_id(token)
    assert result == token
    assert result != "user-local"


# ---------------------------------------------------------------------------
# Opaque token cases
# ---------------------------------------------------------------------------


@patch("flow44.api.auth.settings")
def test_opaque_token_require_jwt_raises(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = True
    mock_settings.AUTH_JWT_SECRET = SECRET
    with pytest.raises(HTTPException) as exc:
        extract_user_id("some-opaque-api-key")
    assert exc.value.status_code == 401
    assert "JWT" in exc.value.detail


@patch("flow44.api.auth.settings")
def test_opaque_token_no_require_returns_as_user_id(mock_settings):
    mock_settings.AUTH_REQUIRE_JWT = False
    mock_settings.AUTH_JWT_SECRET = None
    assert extract_user_id("my-opaque-key") == "my-opaque-key"
