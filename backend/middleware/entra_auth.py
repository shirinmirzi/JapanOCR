import os
import logging
import json
import base64
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

SKIP_AUTH = os.environ.get("SKIP_AUTH", "false").lower() == "true"
ALLOW_DEV_AUTH = os.environ.get("ALLOW_DEV_AUTH", "false").lower() == "true"

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def _decode_jwt_payload(token: str) -> dict:
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
    try:
        claims = _decode_jwt_payload(token)
        return claims
    except Exception as e:
        raise ValueError(f"Failed to decode token: {e}") from e


def extract_user_from_claims(claims: dict) -> dict:
    username = (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
        or claims.get("sub", "unknown")
    )
    name = claims.get("name") or claims.get("given_name", "") + " " + claims.get("family_name", "")
    name = name.strip() or username
    return {
        "username": username,
        "name": name,
        "oid": claims.get("oid", ""),
        "email": claims.get("email") or claims.get("preferred_username", ""),
    }


async def get_current_user(request: Request) -> dict:
    if SKIP_AUTH:
        return {"username": "dev_user", "name": "Dev User", "oid": "dev-oid", "email": "dev@localhost"}

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[len("Bearer "):]

    if ALLOW_DEV_AUTH and token == "dev-token":
        return {"username": "dev_user", "name": "Dev User", "oid": "dev-oid", "email": "dev@localhost"}

    try:
        claims = verify_entra_token(token)
        return extract_user_from_claims(claims)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


async def entra_auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in PUBLIC_PATHS or any(path.startswith(p) for p in ["/docs", "/redoc", "/openapi"]):
        return await call_next(request)

    if SKIP_AUTH:
        request.state.user = {"username": "dev_user", "name": "Dev User", "oid": "dev-oid", "email": "dev@localhost"}
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})

    token = auth_header[len("Bearer "):]

    if ALLOW_DEV_AUTH and token == "dev-token":
        request.state.user = {"username": "dev_user", "name": "Dev User", "oid": "dev-oid", "email": "dev@localhost"}
        return await call_next(request)

    try:
        claims = verify_entra_token(token)
        request.state.user = extract_user_from_claims(claims)
    except ValueError as e:
        return JSONResponse(status_code=401, content={"detail": str(e)})

    return await call_next(request)
