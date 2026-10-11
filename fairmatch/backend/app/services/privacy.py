"""GDPR workflows: data export (Art. 15/20) and account deletion (Art. 17)."""
import uuid
from datetime import date, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.models import (
    Consent,
    DeviceToken,
    Interest,
    Match,
    Message,
    Photo,
    Profile,
    Report,
    Subscription,
    User,
    UserStatus,
)
from app.services import interests
from app.services.app_config import get_config
from app.services.audit import audit
from app.services.safety import revoke_sessions
from app.services.storage import storage


def export_user_data(db: Session, user_id: uuid.UUID) -> dict:
    u = db.get(User, user_id)
    p = u.profile
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "account": {
            "id": str(u.id), "email": u.email, "date_of_birth": iso(u.date_of_birth), "status": u.status,
            "created_at": iso(u.created_at), "verification_status": u.verification_status, "age_assurance": u.age_assurance,
        },
        "profile": None if p is None else {
            c.name: (getattr(p, c.name) if not hasattr(getattr(p, c.name), "isoformat") else iso(getattr(p, c.name)))
            for c in Profile.__table__.columns if c.name != "user_id"
        },
        "photos": [{"id": str(ph.id), "position": ph.position, "created_at": iso(ph.created_at)} for ph in u.photos],
        "interests_sent": [
            {"to": str(i.to_user_id), "state": i.state, "created_at": iso(i.created_at)}
            for i in db.scalars(select(Interest).where(Interest.from_user_id == user_id))
        ],
        "interests_received_count": len(db.scalars(select(Interest.id).where(Interest.to_user_id == user_id)).all()),
        "matches": [
            {"id": str(m.id), "state": m.state, "created_at": iso(m.created_at)}
            for m in db.scalars(select(Match).where(or_(Match.user_low_id == user_id, Match.user_high_id == user_id)))
        ],
        "messages_sent": [
            {"match_id": str(m.match_id), "body": m.body, "created_at": iso(m.created_at)}
            for m in db.scalars(select(Message).where(Message.sender_id == user_id, Message.deleted.is_(False)))
        ],
        "reports_filed": [
            {"reason": r.reason, "created_at": iso(r.created_at), "status": r.status}
            for r in db.scalars(select(Report).where(Report.reporter_id == user_id))
        ],
        "consents": [
            {"kind": c.kind, "granted": c.granted, "version": c.version, "at": iso(c.created_at)}
            for c in db.scalars(select(Consent).where(Consent.user_id == user_id))
        ],
        "subscriptions": [
            {"product_id": s.product_id, "status": s.status, "expires_at": iso(s.expires_at)}
            for s in db.scalars(select(Subscription).where(Subscription.user_id == user_id))
        ],
        "generated_at": utcnow().isoformat(),
    }


def request_deletion(db: Session, user: User) -> None:
    """Immediately hides the account and revokes sessions; data is purged after a grace period."""
    now = utcnow()
    interests.lock_users(db, user.id)
    user.status = UserStatus.PENDING_DELETION.value
    user.deletion_requested_at = now
    revoke_sessions(db, user)
    interests.bulk_mark_user_gone(db, user.id, now)
    for m in db.scalars(select(Match).where(or_(Match.user_low_id == user.id, Match.user_high_id == user.id), Match.state == "active")):
        m.state, m.ended_at, m.ended_by = "unmatched", now, user.id
    audit(db, "privacy.deletion_requested", user.id, "user", user.id)
    db.commit()


def purge_user(db: Session, user_id: uuid.UUID) -> None:
    """Irreversibly removes personal data. The user row is kept as a tombstone (no PII) so that
    foreign keys and abuse prevention (e.g. ban evasion counters) remain consistent."""
    u = db.get(User, user_id)
    if u is None:
        return
    for ph in list(u.photos):
        storage().delete(ph.storage_key)
    db.execute(update(Message).where(Message.sender_id == user_id).values(body="", deleted=True))
    for model in (Photo, DeviceToken, Consent):
        for row in db.scalars(select(model).where(model.user_id == user_id)):
            db.delete(row)
    if u.profile:
        db.delete(u.profile)
    u.email = f"deleted-{u.id}@deleted.invalid"
    u.password_hash = "!"
    u.date_of_birth = date(1900, 1, 1)
    u.status = UserStatus.DELETED.value
    audit(db, "privacy.purged", None, "user", user_id)
    db.commit()


def purge_due(db: Session) -> int:
    cfg = get_config(db)
    cutoff = utcnow() - timedelta(days=cfg["safety"]["deletion_grace_days"])
    ids = db.scalars(
        select(User.id).where(User.status == UserStatus.PENDING_DELETION.value, User.deletion_requested_at <= cutoff)
    ).all()
    for uid in ids:
        purge_user(db, uid)
    return len(ids)
