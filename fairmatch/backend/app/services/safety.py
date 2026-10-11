"""Blocking, reporting, unmatching, suspicious-account heuristics and moderation actions."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.errors import bad_request, not_found
from app.models import Block, Match, RefreshToken, Report, User, UserStatus
from app.services import interests
from app.services.app_config import get_config
from app.services.audit import audit
from app.services.realtime import hub

REPORT_REASONS = {"fake_profile", "harassment", "underage", "spam", "inappropriate", "scam", "other"}


def block(db: Session, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> None:
    if blocker_id == blocked_id:
        raise bad_request("invalid", "You cannot block yourself")
    now = utcnow()
    cfg = get_config(db)
    closed_match = None
    try:
        users = interests.lock_users(db, blocker_id, blocked_id)
        if blocked_id not in users:
            raise not_found("User")
        if db.get(Block, (blocker_id, blocked_id)) is None:
            db.add(Block(blocker_id=blocker_id, blocked_id=blocked_id))
        low, high = sorted((blocker_id, blocked_id))
        m = db.scalars(select(Match).where(Match.user_low_id == low, Match.user_high_id == high)).first()
        if m and m.state == "active":
            m.state, m.ended_at, m.ended_by = "blocked", now, blocker_id
            closed_match = m
        interests.close_between(db, blocker_id, blocked_id, "blocked", now, cfg)
        db.commit()
    except IntegrityError:
        db.rollback()
    except Exception:
        db.rollback()
        raise
    if closed_match is not None:
        hub.publish(blocked_id, {"type": "match_closed", "match_id": str(closed_match.id)})


def unblock(db: Session, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> None:
    b = db.get(Block, (blocker_id, blocked_id))
    if b:
        db.delete(b)
        db.commit()


def unmatch(db: Session, user_id: uuid.UUID, match_id: uuid.UUID) -> None:
    m = db.get(Match, match_id)
    if m is None or not m.includes(user_id):
        raise not_found("Match")
    if m.state == "active":
        m.state, m.ended_at, m.ended_by = "unmatched", utcnow(), user_id
        db.commit()
        hub.publish(m.other(user_id), {"type": "match_closed", "match_id": str(m.id)})


def report(db: Session, reporter_id: uuid.UUID, reported_id: uuid.UUID, reason: str, details: str, also_block: bool) -> Report:
    if reason not in REPORT_REASONS:
        raise bad_request("invalid_reason", "Unknown report reason")
    if reporter_id == reported_id:
        raise bad_request("invalid", "You cannot report yourself")
    target = db.get(User, reported_id)
    if target is None:
        raise not_found("User")
    r = Report(reporter_id=reporter_id, reported_id=reported_id, reason=reason, details=(details or "")[:2000])
    db.add(r)
    db.flush()
    cfg = get_config(db)
    distinct = db.scalar(
        select(func.count(func.distinct(Report.reporter_id))).where(Report.reported_id == reported_id, Report.status == "open")
    )
    # Underage reports or several independent reporters hide the account until a moderator reviews it.
    if target.status == UserStatus.ACTIVE.value and (
        reason == "underage" or distinct >= cfg["safety"]["auto_review_distinct_reporters"]
    ):
        target.status = UserStatus.UNDER_REVIEW.value
        audit(db, "auto_under_review", None, "user", reported_id, reason=reason, distinct_reporters=distinct)
    target.suspicion_score += 3
    db.commit()
    if also_block:
        block(db, reporter_id, reported_id)
    return r


def flag_suspicious(db: Session, user_id: uuid.UUID, points: int, signal: str) -> None:
    """Accumulate heuristic suspicion; above a threshold the account is hidden for review."""
    u = db.get(User, user_id)
    if u is None:
        return
    u.suspicion_score += points
    if u.suspicion_score >= 20 and u.status == UserStatus.ACTIVE.value:
        u.status = UserStatus.UNDER_REVIEW.value
        audit(db, "auto_under_review", None, "user", user_id, signal=signal, score=u.suspicion_score)


def revoke_sessions(db: Session, user: User) -> None:
    user.token_version += 1
    now = utcnow()
    for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))):
        t.revoked_at = now


MODERATION_ACTIONS = {"dismiss", "warn", "suspend", "ban", "restore"}


def moderate(db: Session, actor: User, report_id: uuid.UUID | None, user_id: uuid.UUID, action: str, note: str, ip: str | None) -> None:
    if action not in MODERATION_ACTIONS:
        raise bad_request("invalid_action", "Unknown moderation action")
    now = utcnow()
    target = db.get(User, user_id)
    if target is None:
        raise not_found("User")
    if action in ("suspend", "ban"):
        interests.lock_users(db, user_id)
        target.status = UserStatus.SUSPENDED.value if action == "suspend" else UserStatus.BANNED.value
        revoke_sessions(db, target)
        interests.bulk_mark_user_gone(db, user_id, now)
    elif action == "restore":
        target.status = UserStatus.ACTIVE.value
        target.suspicion_score = 0
    q = select(Report).where(Report.reported_id == user_id, Report.status == "open")
    if report_id is not None:
        q = q.where(Report.id == report_id)
    for r in db.scalars(q):
        r.status = "dismissed" if action in ("dismiss", "restore") else "actioned"
        r.handled_by, r.handled_at, r.resolution = actor.id, now, action
    audit(db, f"moderation.{action}", actor.id, "user", user_id, ip=ip, report_id=str(report_id) if report_id else None, note=note[:500])
    db.commit()
