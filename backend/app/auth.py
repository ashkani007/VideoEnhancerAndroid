"""Client authentication: an operator-issued API key is exchanged for a short-lived token."""
from __future__ import annotations

import hashlib
import hmac
import time

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def client_id_for_key(key: str) -> str:
    """Stable, non-reversible client identifier (never store or log the key itself)."""
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def verify_api_key(key: str | None, settings: Settings) -> str:
    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing API key")
    for k in settings.api_key_list():
        if hmac.compare_digest(k.encode(), key.encode()):
            return client_id_for_key(k)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")


def issue_token(client: str, settings: Settings) -> tuple[str, int]:
    secret = settings.token_secret.get_secret_value()
    if len(secret) < 32:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Server token secret is not configured")
    exp = int(time.time()) + settings.token_ttl_seconds
    return jwt.encode({"sub": client, "exp": exp, "typ": "vrv"}, secret, algorithm="HS256"), exp


def require_client(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    enforce_https(request, settings)
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        claims = jwt.decode(creds.credentials, settings.token_secret.get_secret_value(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None
    if claims.get("typ") != "vrv":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return str(claims["sub"])


def enforce_https(request: Request, settings: Settings) -> None:
    if not settings.require_https:
        return
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    if proto != "https":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "HTTPS required")
