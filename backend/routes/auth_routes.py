"""
Japan OCR Tool - Authentication Routes

Exposes REST endpoints for user identity and token verification. Delegates
all JWT validation to the Entra auth middleware helpers.

Key Features:
- GET /auth/me: returns the caller's profile including computed initials
- POST /auth/verify-token: validates a raw JWT and returns decoded user info
- GET /auth/logout: stateless logout acknowledgement for SPA clients

Dependencies: FastAPI, middleware.entra_auth
Author: SHIRIN MIRZI M K
"""

import logging

from fastapi import APIRouter, Depends

from middleware.entra_auth import extract_user_from_claims, get_current_user, verify_entra_token

logger = logging.getLogger(__name__)
router = APIRouter()


def compute_initials(name: str) -> str:
    """
    Derive up to two uppercase initials from a full display name.

    Args:
        name: Full name string, e.g. "Jane Doe" or a single word.

    Returns:
        Two-character uppercase string from the first and last name tokens,
        one character when only a single token is present, or "?" for empty
        input.
    """
    if not name:
        return "?"
    parts = [p for p in name.strip().split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper() if parts else "?"


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    Return the authenticated user's profile including computed initials.

    Returns:
        User profile dict (username, name, oid, email) extended with an
        'initials' key derived from the display name.
    """
    return {
        **user,
        "initials": compute_initials(user.get("name", "")),
    }


@router.post("/auth/verify-token")
async def verify_token(body: dict):
    """
    Validate a raw JWT and return the decoded user profile.

    Args:
        body: JSON body containing a 'token' key with the bearer token string.

    Returns:
        Dict with 'valid' (bool) and 'user' (profile dict or None).
    """
    token = body.get("token", "")
    if not token:
        return {"valid": False, "user": None}
    try:
        claims = verify_entra_token(token)
        user = extract_user_from_claims(claims)
        return {"valid": True, "user": user}
    except ValueError:
        return {"valid": False, "user": None}


@router.get("/auth/logout")
async def logout():
    """
    Acknowledge a logout request from the SPA client.

    Token invalidation is handled client-side; this endpoint exists so the
    SPA can make a clean HTTP call before clearing its local token storage.

    Returns:
        Dict with 'logged_out': True.
    """
    return {"logged_out": True}
