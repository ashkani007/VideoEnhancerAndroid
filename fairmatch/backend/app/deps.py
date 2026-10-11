import uuid

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.db import get_db
from app.errors import AppError, forbidden
from app.models import Role, User, UserStatus
from app.security import decode_access_token

ALLOWED_STATUSES = {UserStatus.ACTIVE.value, UserStatus.UNDER_REVIEW.value}


def user_from_token(db: Session, token: str) -> User:
    try:
        payload = decode_access_token(token)
        uid = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise AppError(401, "invalid_token", "Please sign in again")
    user = db.get(User, uid)
    if user is None or user.token_version != payload.get("tv"):
        raise AppError(401, "invalid_token", "Please sign in again")
    if user.status not in ALLOWED_STATUSES:
        raise AppError(403, "account_unavailable", "This account is not available")
    return user


def current_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "unauthenticated", "Sign in required")
    user = user_from_token(db, authorization.split(" ", 1)[1].strip())
    now = utcnow()
    if user.last_active_at is None or (now - user.last_active_at).total_seconds() > 300:
        user.last_active_at = now
        db.commit()
    return user


def require_role(*roles: Role):
    allowed = {r.value for r in roles}

    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise forbidden("Insufficient permissions")
        return user

    return dep


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
