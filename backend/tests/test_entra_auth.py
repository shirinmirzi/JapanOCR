"""
Japan OCR Tool - Entra Auth Middleware Tests

Unit tests for the JWT decoding, user profile extraction, and authentication
middleware helpers in middleware.entra_auth.

Author: SHIRIN MIRZI M K
"""

import base64
import json

import pytest
from fastapi.testclient import TestClient

import main
from middleware.entra_auth import (
    _decode_jwt_payload,
    extract_user_from_claims,
    verify_entra_token,
)

# =============================================================================
# _decode_jwt_payload
# =============================================================================


def _make_jwt(payload: dict) -> str:
    """Build a syntactically valid JWT with the given payload (unsigned)."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{encoded}.signature"


def test_decode_jwt_payload_returns_claims() -> None:
    claims = {"oid": "test-oid", "preferred_username": "user@example.com"}
    token = _make_jwt(claims)
    decoded = _decode_jwt_payload(token)
    assert decoded["oid"] == "test-oid"
    assert decoded["preferred_username"] == "user@example.com"


def test_decode_jwt_payload_raises_on_malformed_token() -> None:
    with pytest.raises(ValueError):
        _decode_jwt_payload("not-a-jwt")


def test_decode_jwt_payload_raises_on_invalid_base64() -> None:
    with pytest.raises(ValueError):
        _decode_jwt_payload("header.!!!invalid!!!.signature")


# =============================================================================
# verify_entra_token
# =============================================================================


def test_verify_entra_token_returns_claims() -> None:
    claims = {"oid": "abc", "name": "Test User"}
    token = _make_jwt(claims)
    result = verify_entra_token(token)
    assert result["oid"] == "abc"
    assert result["name"] == "Test User"


def test_verify_entra_token_raises_value_error_for_bad_token() -> None:
    with pytest.raises(ValueError, match="Failed to decode token"):
        verify_entra_token("bad.token")


# =============================================================================
# extract_user_from_claims
# =============================================================================


def test_extract_user_from_claims_uses_preferred_username() -> None:
    claims = {
        "preferred_username": "user@corp.com",
        "name": "Jane Doe",
        "oid": "oid-1",
        "email": "user@corp.com",
    }
    user = extract_user_from_claims(claims)
    assert user["username"] == "user@corp.com"
    assert user["name"] == "Jane Doe"
    assert user["oid"] == "oid-1"
    assert user["email"] == "user@corp.com"


def test_extract_user_from_claims_falls_back_to_upn() -> None:
    claims = {"upn": "upn@corp.com", "oid": "oid-2"}
    user = extract_user_from_claims(claims)
    assert user["username"] == "upn@corp.com"


def test_extract_user_from_claims_falls_back_to_sub() -> None:
    claims = {"sub": "sub-value", "oid": "oid-3"}
    user = extract_user_from_claims(claims)
    assert user["username"] == "sub-value"


def test_extract_user_from_claims_builds_name_from_given_family() -> None:
    # When 'name' is absent, combine given_name + family_name.
    claims = {
        "sub": "u",
        "given_name": "Jane",
        "family_name": "Doe",
        "oid": "",
    }
    user = extract_user_from_claims(claims)
    assert user["name"] == "Jane Doe"


def test_extract_user_from_claims_missing_email_falls_back() -> None:
    claims = {"preferred_username": "user@corp.com", "oid": "x"}
    user = extract_user_from_claims(claims)
    # email should fall back to preferred_username when email claim is absent
    assert user["email"] == "user@corp.com"


# =============================================================================
# Middleware integration (SKIP_AUTH path)
# =============================================================================


def test_middleware_passes_through_on_skip_auth(monkeypatch) -> None:
    monkeypatch.setattr("middleware.entra_auth.SKIP_AUTH", True)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_middleware_returns_401_for_missing_auth_header(monkeypatch) -> None:
    monkeypatch.setattr("middleware.entra_auth.SKIP_AUTH", False)
    monkeypatch.setattr("middleware.entra_auth.ALLOW_DEV_AUTH", False)

    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.get("/auth/me")

    assert response.status_code == 401


def test_middleware_allows_dev_token_when_allow_dev_auth(monkeypatch) -> None:
    monkeypatch.setattr("middleware.entra_auth.SKIP_AUTH", False)
    monkeypatch.setattr("middleware.entra_auth.ALLOW_DEV_AUTH", True)

    with TestClient(main.app) as client:
        response = client.get("/auth/me", headers={"Authorization": "Bearer dev-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "dev_user"
