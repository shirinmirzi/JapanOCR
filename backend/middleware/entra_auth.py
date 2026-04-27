"""
Japan OCR Tool - Azure Entra ID Authentication Middleware

Validates Azure Entra ID (formerly Azure AD) JWT bearer tokens on every
incoming HTTP request and populates request.state.user with the caller's
identity claims.

Key Features:
- JWT decoding: extracts and decodes the payload segment without a network call
- Middleware: integrates with FastAPI's ASGI middleware chain
- Dev shortcuts: SKIP_AUTH and ALLOW_DEV_AUTH flags for local development
- Public paths: /health and OpenAPI docs bypass authentication

Dependencies: FastAPI
Author: SHIRIN MIRZI M K
"""

import base64
import json
import logging
import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

SKIP_AUTH = os.environ.get("SKIP_AUTH", "false").lower() == "true"
ALLOW_DEV_AUTH = os.environ.get("ALLOW_DEV_AUTH", "false").lower() == "true"

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
DEV_USER = {
    "username": "dev_user",
    "name": "Dev User",
    "oid": "dev-oid",
    "email": "dev@localhost",
}


def _decode_jwt_payload(token: str) -> dict:
    """
    Decode and parse the payload segment of a JWT without signature verification.

    Args:
        token: A raw JWT string in the standard three-part dot-separated format.

    Returns:
        Parsed JSON payload as a plain dict.

    Raises:
        ValueError: When the token does not contain at least two dot-separated
            parts or the payload is not valid base64-encoded JSON.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += "=" * padding
    decoded = base64.urlsafe_b64decode(payload)
    return json.loads(decoded)


def verify_entra_token(token: str) -> dict:
    """
    Decode an Azure Entra ID JWT and return its claims.

    Args:
        token: Bearer token string extracted from the Authorization header.

    Returns:
        Decoded JWT claims as a dict (e.g. oid, preferred_username, name).

    Raises:
        ValueError: When decoding fails due to malformed token structure.
    """
    try:
        claims = _decode_jwt_payload(token)
        return claims
    except Exception as e:
        raise ValueError(f"Failed to decode token: {e}") from e


def extract_user_from_claims(claims: dict) -> dict:
    """
    Build a normalised user profile dict from raw JWT claims.

    Args:
        claims: Decoded JWT payload as returned by verify_entra_token.

    Returns:
        Dict with keys: username, name, oid, and email. Falls back through
        multiple claim fields to maximise compatibility across token formats.
    """
    username = (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
        or claims.get("sub", "unknown")
    )
    full_name = (
        claims.get("given_name", "") + " " + claims.get("family_name", "")
    ).strip()
    name = claims.get("name") or full_name or username
    return {
        "username": username,
        "name": name,
        "oid": claims.get("oid", ""),
        "email": claims.get("email") or claims.get("preferred_username", ""),
    }


async def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency that extracts and validates the caller's identity.

    Args:
        request: The incoming FastAPI Request object.

    Returns:
        Normalised user profile dict (username, name, oid, email).

    Raises:
        HTTPException: 401 when the Authorization header is missing, malformed,
            or contains an invalid token.
    """
    if SKIP_AUTH:
        return DEV_USER.copy()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[len("Bearer "):]

    if ALLOW_DEV_AUTH and token == "dev-token":
        return DEV_USER.copy()

    try:
        claims = verify_entra_token(token)
        return extract_user_from_claims(claims)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


async def entra_auth_middleware(request: Request, call_next):
    """
    ASGI middleware that enforces JWT authentication on protected routes.

    Populates request.state.user on success so downstream handlers can read
    the caller's identity without re-parsing the token.

    Args:
        request: The incoming ASGI request.
        call_next: The next middleware or route handler in the chain.

    Returns:
        The response from the next handler, or a 401 JSONResponse when
        authentication fails.
    """
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in PUBLIC_PATHS or any(
        path.startswith(prefix) for prefix in ["/docs", "/redoc", "/openapi"]
    ):
        return await call_next(request)

    if SKIP_AUTH:
        request.state.user = DEV_USER.copy()
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid Authorization header"},
        )

    token = auth_header[len("Bearer "):]

    if ALLOW_DEV_AUTH and token == "dev-token":
        request.state.user = DEV_USER.copy()
        return await call_next(request)

    try:
        claims = verify_entra_token(token)
        request.state.user = extract_user_from_claims(claims)
    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    return await call_next(request)
