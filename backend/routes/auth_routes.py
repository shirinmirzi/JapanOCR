import logging
from fastapi import APIRouter, Depends, HTTPException
from middleware.entra_auth import get_current_user, verify_entra_token, extract_user_from_claims

logger = logging.getLogger(__name__)
router = APIRouter()


def compute_initials(name: str) -> str:
    if not name:
        return "?"
    parts = [p for p in name.strip().split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper() if parts else "?"


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        **user,
        "initials": compute_initials(user.get("name", "")),
    }


@router.post("/auth/verify-token")
async def verify_token(body: dict):
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
    return {"logged_out": True}
