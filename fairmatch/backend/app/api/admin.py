"""Moderation & operations. Every mutating action is written to the audit log."""
import uuid

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import client_ip, require_role
from app.errors import bad_request, not_found
from app.models import AuditLog, Report, Role, User
from app.schemas import ModerationIn
from app.services import app_config, pairing, safety
from app.services.audit import audit

router = APIRouter(prefix="/admin", tags=["admin"])
moderator = require_role(Role.MODERATOR, Role.ADMIN)
admin = require_role(Role.ADMIN)


@router.get("/reports")
def reports(status: str = "open", db: Session = Depends(get_db), actor: User = Depends(moderator)):
    rows = db.scalars(select(Report).where(Report.status == status).order_by(Report.created_at).limit(100)).all()
    return {"reports": [
        {"id": str(r.id), "reported_id": str(r.reported_id), "reporter_id": str(r.reporter_id) if r.reporter_id else None,
         "reason": r.reason, "details": r.details, "created_at": r.created_at.isoformat(), "status": r.status}
        for r in rows
    ]}


@router.post("/moderate")
def moderate(body: ModerationIn, request: Request, db: Session = Depends(get_db), actor: User = Depends(moderator)):
    if body.action == "ban" and actor.role != Role.ADMIN.value:
        raise bad_request("admin_required", "Only admins can ban")
    safety.moderate(db, actor, body.report_id, body.user_id, body.action, body.note, client_ip(request))
    return {"ok": True}


@router.post("/users/{user_id}/verification")
def set_verification(user_id: uuid.UUID, status: str = Body(embed=True), request: Request = None,
                     db: Session = Depends(get_db), actor: User = Depends(moderator)):
    if status not in ("verified", "rejected", "pending", "unverified"):
        raise bad_request("invalid_status", "Unknown verification status")
    u = db.get(User, user_id)
    if u is None:
        raise not_found("User")
    u.verification_status = status
    audit(db, "moderation.verification", actor.id, "user", user_id, ip=client_ip(request), status=status)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/age-assurance")
def set_age_assurance(user_id: uuid.UUID, level: str = Body(embed=True), request: Request = None,
                      db: Session = Depends(get_db), actor: User = Depends(moderator)):
    if level not in ("self_declared", "estimated", "document_verified"):
        raise bad_request("invalid_level", "Unknown assurance level")
    u = db.get(User, user_id)
    if u is None:
        raise not_found("User")
    u.age_assurance = level
    audit(db, "moderation.age_assurance", actor.id, "user", user_id, ip=client_ip(request), level=level)
    db.commit()
    return {"ok": True}


@router.get("/config")
def get_config(db: Session = Depends(get_db), actor: User = Depends(admin)):
    return app_config.get_config(db)


@router.put("/config/{key}")
def put_config(key: str, value: dict = Body(...), request: Request = None, db: Session = Depends(get_db), actor: User = Depends(admin)):
    try:
        app_config.set_override(db, key, value, actor.id)
    except KeyError:
        raise bad_request("unknown_key", f"Unknown config section '{key}'")
    audit(db, "config.update", actor.id, "config", key, ip=client_ip(request), value=value)
    db.commit()
    return app_config.get_config(db)[key]


@router.get("/fairness")
def fairness(db: Session = Depends(get_db), actor: User = Depends(moderator)):
    return pairing.exposure_snapshot(db)


@router.get("/audit")
def audit_log(limit: int = 100, db: Session = Depends(get_db), actor: User = Depends(admin)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))).all()
    return {"entries": [
        {"id": r.id, "actor_id": str(r.actor_id) if r.actor_id else None, "action": r.action, "target_type": r.target_type,
         "target_id": r.target_id, "details": r.details, "created_at": r.created_at.isoformat()}
        for r in rows
    ]}
