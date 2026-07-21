"""Tests for get_user_id, decode_token, and TokenPayload.

A valid signed JWT carrying an ``/emailaddress`` claim is always required — there is no
anonymous or opaque-token fallback. Tokens are signed/verified with RS256 (as in
production) using a keypair generated for the test session.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from pydantic import ValidationError

from flow44.api.deps import TokenPayload, decode_token, get_user_id
from flow44.config import settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALGORITHM = "RS256"  # matches production


def _gen_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


PRIVATE_KEY, PUBLIC_KEY = _gen_keypair()
WRONG_PRIVATE_KEY, _ = _gen_keypair()

# Claim keys are matched by URL suffix (case-sensitive). ``get_user_id`` resolves
# identity from the ``/emailaddress`` claim; ``/UniqueID`` still surfaces on the
# payload as ``unique_id``.
CLAIM_PREFIX = "https://issuer.example/v1/claims/"
CLAIM_EMAIL_URL = CLAIM_PREFIX + "emailaddress"
CLAIM_UNIQUE_ID_URL = CLAIM_PREFIX + "UniqueID"


def _make_jwt(claims: dict, key: str = PRIVATE_KEY, algorithm: str = ALGORITHM) -> str:
    """Sign a token, adding a future ``exp`` by default (pass ``exp`` to override)."""
    payload = {"exp": int(time.time()) + 3600, **claims}
    return jwt.encode(payload, key, algorithm=algorithm)


@pytest.fixture(autouse=True)
def _use_test_key(monkeypatch):
    # raising=True (default) makes a renamed setting fail loudly instead of silently passing.
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY", PUBLIC_KEY)
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", ALGORITHM)


# ---------------------------------------------------------------------------
# No token
# ---------------------------------------------------------------------------


class TestNoToken:
    def test_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            get_user_id(None)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# get_user_id with a JWT
# ---------------------------------------------------------------------------


class TestJwt:
    def test_url_email_claim_returned(self):
        token = _make_jwt({CLAIM_EMAIL_URL: "user-123@corp.local"})
        assert get_user_id(token) == "user-123@corp.local"

    def test_first_matching_url_claim_wins(self):
        token = _make_jwt(
            {
                "https://other.example/claims/emailaddress": "first@corp.local",
                CLAIM_EMAIL_URL: "second@corp.local",
            }
        )
        assert get_user_id(token) == "first@corp.local"

    def test_no_email_claim_rejected(self):
        """Signed, unexpired token without an emailaddress claim → 401 missing identification."""
        token = _make_jwt({"sub": "ignored", "role": "admin"})
        with pytest.raises(HTTPException) as exc:
            get_user_id(token)
        assert exc.value.status_code == 401
        assert "missing user identification" in exc.value.detail.lower()

    def test_expired_token_rejected(self):
        token = _make_jwt({CLAIM_UNIQUE_ID_URL: "user-x", "exp": int(time.time()) - 10})
        with pytest.raises(HTTPException) as exc:
            get_user_id(token)
        assert exc.value.status_code == 401
        assert "invalid or expired" in exc.value.detail.lower()

    def test_unexpired_token_accepted(self):
        token = _make_jwt({CLAIM_EMAIL_URL: "user-y@corp.local"})
        assert get_user_id(token) == "user-y@corp.local"

    def test_malformed_token_rejected(self):
        # Exactly two dots; payload segment decodes to non-JSON bytes.
        bad = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YWFh.YWFh"
        with pytest.raises(HTTPException) as exc:
            get_user_id(bad)
        assert exc.value.status_code == 401
        assert "invalid or expired" in exc.value.detail.lower()

    def test_bad_signature_rejected(self):
        token = _make_jwt({CLAIM_UNIQUE_ID_URL: "user-z"}, key=WRONG_PRIVATE_KEY)
        with pytest.raises(HTTPException) as exc:
            get_user_id(token)
        assert exc.value.status_code == 401
        assert "invalid or expired" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# Opaque (non-JWT) tokens — no special path, fail decode like any bad token
# ---------------------------------------------------------------------------


class TestOpaque:
    def test_rejected(self):
        with pytest.raises(HTTPException) as exc:
            get_user_id("some-opaque-api-key")
        assert exc.value.status_code == 401
        assert "invalid or expired" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# decode_token
# ---------------------------------------------------------------------------


class TestDecodeToken:
    def test_returns_payload_on_valid_jwt(self):
        token = _make_jwt({CLAIM_UNIQUE_ID_URL: "u-1", "iss": "test-issuer"})
        payload = decode_token(token)
        assert isinstance(payload, TokenPayload)
        assert payload.unique_id == "u-1"
        assert payload.iss == "test-issuer"

    def test_returns_none_on_garbage(self):
        assert decode_token("not-a-jwt") is None
        assert decode_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.YWFh.YWFh") is None

    def test_returns_none_when_missing_exp(self):
        """Signature verifies but the payload lacks the required ``exp`` → validation fails."""
        token = jwt.encode({CLAIM_UNIQUE_ID_URL: "u"}, PRIVATE_KEY, algorithm=ALGORITHM)
        assert decode_token(token) is None


# ---------------------------------------------------------------------------
# TokenPayload model (pure — no settings needed)
# ---------------------------------------------------------------------------


class TestTokenPayload:
    def test_lifts_all_url_suffixed_claims(self):
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

    def test_unique_id_is_none_when_claim_absent(self):
        payload = TokenPayload.model_validate({"sub": "x", "exp": 1700000000})
        assert payload.unique_id is None

    def test_preserves_unknown_claims_via_extra(self):
        payload = TokenPayload.model_validate(
            {
                CLAIM_PREFIX + "UniqueID": "u",
                "exp": 1700000000,
                "custom_role": "admin",
                "sub": "ignored-by-model",
            }
        )
        dumped = payload.model_dump()
        assert dumped["custom_role"] == "admin"
        assert dumped["sub"] == "ignored-by-model"

    def test_first_url_suffix_match_wins(self):
        payload = TokenPayload.model_validate(
            {
                "https://other.example/claims/UniqueID": "first",
                CLAIM_PREFIX + "UniqueID": "second",
                "exp": 1700000000,
            }
        )
        assert payload.unique_id == "first"

    def test_missing_exp_raises(self):
        with pytest.raises(ValidationError):
            TokenPayload.model_validate({CLAIM_PREFIX + "UniqueID": "u"})
