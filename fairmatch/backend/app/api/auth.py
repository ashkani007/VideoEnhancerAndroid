import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.config import get_settings
from app.db import get_db
from app.deps import client_ip, current_user
from app.errors import AppError, bad_request
from app.models import Consent, RefreshToken, User
from app.schemas import LoginIn, RefreshIn, RegisterIn, TokenOut
from app.security import DUMMY_HASH, create_access_token, hash_password, hash_token, new_refresh_token, verify_password
from app.services.audit import audit
from app.services.persona import age_on
from app.services.ratelimit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue(db: Session, user: User, family: uuid.UUID | None = None) -> TokenOut:
    raw, digest = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id, family_id=family or uuid.uuid4(), token_hash=digest,
            expires_at=utcnow() + timedelta(days=get_settings().refresh_token_days),
        )
    )
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role, user.token_version), refresh_token=raw, user_id=user.id)


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request) or "unknown"
    limiter.enforce(f"register:{ip}", 10, 3600)
    if not (body.accept_terms and body.accept_privacy):
        raise bad_request("consent_required", "Please accept the Terms and Privacy Policy")
    today = utcnow().date()
    age = age_on(body.date_of_birth, today)
    if age < 18:
        # Nothing is stored for under-18 attempts.
        raise AppError(403, "underage", "FairMatch is only available to adults aged 18 or older")
    if age > 110:
        raise bad_request("invalid_dob", "Please enter a valid date of birth")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), date_of_birth=body.date_of_birth)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists")
    db.add_all([Consent(user_id=user.id, kind="terms", granted=True), Consent(user_id=user.id, kind="privacy", granted=True)])
    audit(db, "auth.register", user.id, "user", user.id, ip=ip)
    return _issue(db, user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request) or "unknown"
    email = body.email.lower()
    limiter.enforce(f"login:{ip}", 30, 300)
    limiter.enforce(f"login:{email}", 10, 300)
    user = db.scalars(select(User).where(User.email == email)).first()
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise AppError(401, "invalid_credentials", "Email or password is incorrect")
    if user.status in ("banned", "suspended", "deleted"):
        raise AppError(403, "account_unavailable", "This account is not available")
    if user.status == "pending_deletion":
        raise AppError(403, "account_pending_deletion", "This account is scheduled for deletion")
    return _issue(db, user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    now = utcnow()
    tok = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token)).with_for_update()).first()
    if tok is None or tok.expires_at <= now:
        raise AppError(401, "invalid_token", "Please sign in again")
    if tok.revoked_at is not None:
        # Reuse of a rotated token: assume theft, revoke the whole family.
        for t in db.scalars(select(RefreshToken).where(RefreshToken.family_id == tok.family_id)):
            t.revoked_at = t.revoked_at or now
        audit(db, "auth.refresh_reuse_detected", tok.user_id, "user", tok.user_id)
        db.commit()
        raise AppError(401, "invalid_token", "Please sign in again")
    user = db.get(User, tok.user_id)
    if user is None or user.status not in ("active", "under_review"):
        raise AppError(401, "invalid_token", "Please sign in again")
    tok.revoked_at = now
    return _issue(db, user, family=tok.family_id)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tok = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token))).first()
    if tok and tok.user_id == user.id:
        tok.revoked_at = utcnow()
        db.commit()
