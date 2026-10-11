"""Interest queue, state machine and mutual matching.

Concurrency model
-----------------
Every mutation runs in one PostgreSQL transaction that first locks the `users` rows of
both participants with SELECT ... FOR UPDATE in a deterministic (id) order. That
serialises (a) quota consumption of the sender, (b) pending-capacity checks of the
recipient and (c) mutual-match detection between the two, without deadlocks.
Partial unique indexes (one active interest per ordered pair, one match per unordered
pair) are a second line of defence; violations surface as idempotent results.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.errors import AppError, bad_request, conflict, forbidden, not_found
from app.models import (
    ACTIVE_INTEREST_STATES,
    Block,
    DailyQuota,
    Interest,
    InterestEvent,
    InterestState as S,
    Match,
    PairCandidate,
    PairPresentation,
    User,
)
from app.services import entitlements as ent
from app.services.app_config import get_config
from app.services.push import notify_user
from app.services.realtime import hub

# Allowed transitions of the state machine.
TRANSITIONS: dict[S, set[S]] = {
    S.PROPOSED: {S.SELECTED},
    S.SELECTED: {S.PENDING, S.WAITLISTED, S.MATCHED},
    S.WAITLISTED: {S.PENDING, S.MATCHED, S.EXPIRED, S.CANCELED, S.REJECTED},
    S.PENDING: {S.MATCHED, S.REJECTED, S.EXPIRED, S.CANCELED},
    S.MATCHED: set(),
    S.REJECTED: set(),
    S.EXPIRED: set(),
    S.CANCELED: set(),
}


class InvalidTransition(Exception):
    pass


def can_transition(src: S | None, dst: S) -> bool:
    return src is None and dst == S.SELECTED or (src is not None and dst in TRANSITIONS[src])


def _transition(db: Session, interest: Interest, dst: S, now: datetime, reason: str | None = None) -> None:
    src = S(interest.state) if interest.state else None
    if not can_transition(src, dst):
        raise InvalidTransition(f"{src} -> {dst}")
    interest.state = dst.value
    if dst == S.PENDING:
        interest.delivered_at = now
    if dst in (S.MATCHED, S.REJECTED, S.EXPIRED, S.CANCELED):
        interest.resolved_at = now
        interest.resolution_reason = reason
    db.add(InterestEvent(interest_id=interest.id, from_state=src.value if src else None, to_state=dst.value, reason=reason))


def lock_users(db: Session, *user_ids: uuid.UUID) -> dict[uuid.UUID, User]:
    ids = sorted(set(user_ids))
    users = db.scalars(select(User).where(User.id.in_(ids)).order_by(User.id).with_for_update()).all()
    return {u.id: u for u in users}


def is_blocked(db: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(func.count()).select_from(Block).where(
                or_(and_(Block.blocker_id == a, Block.blocked_id == b), and_(Block.blocker_id == b, Block.blocked_id == a))
            )
        )
        > 0
    )


def pending_count(db: Session, to_user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Interest).where(Interest.to_user_id == to_user_id, Interest.state == S.PENDING.value)
    )


def _quota_row(db: Session, user_id: uuid.UUID, now: datetime) -> DailyQuota:
    day = now.date()
    row = db.scalars(select(DailyQuota).where(DailyQuota.user_id == user_id, DailyQuota.day == day).with_for_update()).first()
    if row is None:
        row = DailyQuota(user_id=user_id, day=day, positive_used=0, boosted_slots=0, total_slots=0)
        db.add(row)
        db.flush()
    return row


def remaining_selections(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> tuple[int, int]:
    now = now or utcnow()
    cfg = get_config(db)
    limit = ent.entitlements(db, cfg, user_id, now)["daily_positive_selections"]
    used = db.scalar(select(DailyQuota.positive_used).where(DailyQuota.user_id == user_id, DailyQuota.day == now.date())) or 0
    return max(0, limit - used), limit


def _create_match(db: Session, a: uuid.UUID, b: uuid.UUID, now: datetime) -> Match:
    low, high = sorted((a, b))
    existing = db.scalars(select(Match).where(Match.user_low_id == low, Match.user_high_id == high)).first()
    if existing:
        if existing.state != "active":
            raise conflict("match_closed", "These users can no longer match")
        return existing
    m = Match(user_low_id=low, user_high_id=high, state="active", created_at=now)
    db.add(m)
    db.flush()
    return m


def _promote_waitlist(db: Session, to_user_id: uuid.UUID, now: datetime, cfg: dict) -> list[Interest]:
    """Deliver waitlisted interests (FIFO) while the recipient has free pending capacity.
    Caller must hold the lock on the recipient's user row."""
    cap = cfg["interest"]["max_incoming_pending"]
    ttl = timedelta(hours=cfg["interest"]["pending_ttl_hours"])
    free = cap - pending_count(db, to_user_id)
    promoted = []
    if free <= 0:
        return promoted
    waiting = db.scalars(
        select(Interest)
        .where(Interest.to_user_id == to_user_id, Interest.state == S.WAITLISTED.value)
        .order_by(Interest.created_at, Interest.id)
        .limit(free)
        .with_for_update(skip_locked=True)
    ).all()
    for it in waiting:
        _transition(db, it, S.PENDING, now, "promoted")
        it.expires_at = now + ttl
        promoted.append(it)
    return promoted


@dataclass
class SelectionResult:
    interest: Interest
    match: Match | None
    idempotent_replay: bool = False


def select_candidate(
    db: Session, viewer_id: uuid.UUID, pair_id: uuid.UUID, chosen_id: uuid.UUID, idempotency_key: str
) -> SelectionResult:
    if not idempotency_key or len(idempotency_key) > 80:
        raise bad_request("idempotency_key_required", "A valid Idempotency-Key is required")
    now = utcnow()
    cfg = get_config(db)
    try:
        # Idempotent replay: same key returns the original outcome without side effects.
        prior = db.scalars(
            select(Interest).where(Interest.from_user_id == viewer_id, Interest.idempotency_key == idempotency_key)
        ).first()
        if prior:
            match = _match_between(db, viewer_id, prior.to_user_id)
            return SelectionResult(prior, match, idempotent_replay=True)

        users = lock_users(db, viewer_id, chosen_id)
        # Re-check under the lock: a concurrent request with the same key may have just committed.
        prior = db.scalars(
            select(Interest).where(Interest.from_user_id == viewer_id, Interest.idempotency_key == idempotency_key)
        ).first()
        if prior:
            db.commit()
            return SelectionResult(prior, _match_between(db, viewer_id, prior.to_user_id), idempotent_replay=True)
        viewer, target = users.get(viewer_id), users.get(chosen_id)
        if viewer is None or target is None:
            raise not_found("User")
        if viewer.status != "active":
            raise forbidden("Account is not active")

        pair = db.scalars(select(PairPresentation).where(PairPresentation.id == pair_id).with_for_update()).first()
        if pair is None or pair.viewer_id != viewer_id:
            raise not_found("Pair")
        cand = next((c for c in pair.candidates if c.candidate_id == chosen_id), None)
        if cand is None:
            raise bad_request("not_in_pair", "That person is not part of this pair")
        if pair.state != "open":
            raise conflict("pair_closed", "This pair has already been resolved")

        if target.status != "active" or is_blocked(db, viewer_id, chosen_id):
            raise conflict("unavailable", "This person is no longer available")

        reverse = db.scalars(
            select(Interest)
            .where(
                Interest.from_user_id == chosen_id,
                Interest.to_user_id == viewer_id,
                Interest.state.in_((S.PENDING.value, S.WAITLISTED.value)),
            )
            .with_for_update()
        ).first()

        # Choosing back someone who already chose you completes a match and is always free.
        quota = _quota_row(db, viewer_id, now)
        limit = ent.entitlements(db, cfg, viewer_id, now)["daily_positive_selections"]
        if reverse is None and quota.positive_used >= limit:
            raise AppError(429, "daily_limit_reached", "You've used today's selections. They refresh tomorrow.", {"limit": limit})

        existing = db.scalars(
            select(Interest).where(
                Interest.from_user_id == viewer_id,
                Interest.to_user_id == chosen_id,
                Interest.state.in_(ACTIVE_INTEREST_STATES),
            )
        ).first()
        if existing:
            raise conflict("already_interested", "You already expressed interest in this person")

        # Resolve the pair.
        pair.state, pair.chosen_id, pair.resolved_at = "chosen", chosen_id, now
        for c in pair.candidates:
            c.state = S.SELECTED.value if c.candidate_id == chosen_id else "PASSED"
        if reverse is None:
            quota.positive_used += 1

        interest = Interest(
            id=uuid.uuid4(), from_user_id=viewer_id, to_user_id=chosen_id, state=None, pair_id=pair_id,
            idempotency_key=idempotency_key, created_at=now,
        )
        db.add(interest)
        _transition(db, interest, S.SELECTED, now)
        db.flush()

        match = None
        if reverse is not None:
            # Mutual interest: both sides confirmed -> match.
            match = _create_match(db, viewer_id, chosen_id, now)
            _transition(db, interest, S.MATCHED, now, "mutual")
            _transition(db, reverse, S.MATCHED, now, "mutual")
            _promote_waitlist(db, viewer_id, now, cfg)
        elif pending_count(db, chosen_id) < cfg["interest"]["max_incoming_pending"]:
            _transition(db, interest, S.PENDING, now)
            interest.expires_at = now + timedelta(hours=cfg["interest"]["pending_ttl_hours"])
        else:
            _transition(db, interest, S.WAITLISTED, now, "recipient_at_capacity")
            interest.expires_at = now + timedelta(hours=cfg["interest"]["waitlist_ttl_hours"])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("already_interested", "You already expressed interest in this person")
    except Exception:
        db.rollback()
        raise

    _after_commit_notifications(db, interest, match)
    return SelectionResult(interest, match)


def _match_between(db: Session, a: uuid.UUID, b: uuid.UUID) -> Match | None:
    low, high = sorted((a, b))
    return db.scalars(select(Match).where(Match.user_low_id == low, Match.user_high_id == high)).first()


def _after_commit_notifications(db: Session, interest: Interest, match: Match | None) -> None:
    if match is not None:
        for uid in (match.user_low_id, match.user_high_id):
            hub.publish(uid, {"type": "match", "match_id": str(match.id)})
            notify_user(db, uid, "It's a match 💜", "You both chose each other. Say hello!", {"type": "match", "match_id": str(match.id)})
    elif interest.state == S.PENDING.value:
        hub.publish(interest.to_user_id, {"type": "interest_received"})
        notify_user(db, interest.to_user_id, "Someone chose you", "Open FairMatch to see who.", {"type": "interest"})


def respond(db: Session, user_id: uuid.UUID, interest_id: uuid.UUID, accept: bool) -> SelectionResult:
    """Recipient accepts or declines a delivered (PENDING) interest."""
    now = utcnow()
    cfg = get_config(db)
    try:
        it = db.get(Interest, interest_id)
        if it is None or it.to_user_id != user_id:
            raise not_found("Interest")
        lock_users(db, it.from_user_id, it.to_user_id)
        db.refresh(it, with_for_update=True)
        if it.state != S.PENDING.value:
            raise conflict("not_pending", f"This request is {it.state.lower()}")
        if it.expires_at and it.expires_at <= now:
            _transition(db, it, S.EXPIRED, now, "ttl")
            _promote_waitlist(db, user_id, now, cfg)
            db.commit()
            raise conflict("expired", "This request has expired")
        match = None
        if accept:
            if is_blocked(db, it.from_user_id, user_id):
                raise conflict("unavailable", "This person is no longer available")
            match = _create_match(db, it.from_user_id, user_id, now)
            _transition(db, it, S.MATCHED, now, "accepted")
            # A reverse active interest (rare) also resolves into the match.
            for rev in db.scalars(
                select(Interest).where(
                    Interest.from_user_id == user_id, Interest.to_user_id == it.from_user_id,
                    Interest.state.in_(ACTIVE_INTEREST_STATES),
                )
            ):
                _transition(db, rev, S.MATCHED, now, "mutual")
        else:
            _transition(db, it, S.REJECTED, now, "declined")
        _promote_waitlist(db, user_id, now, cfg)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if match:
        _after_commit_notifications(db, it, match)
    return SelectionResult(it, match)


def cancel(db: Session, user_id: uuid.UUID, interest_id: uuid.UUID) -> Interest:
    now = utcnow()
    cfg = get_config(db)
    try:
        it = db.get(Interest, interest_id)
        if it is None or it.from_user_id != user_id:
            raise not_found("Interest")
        lock_users(db, it.from_user_id, it.to_user_id)
        db.refresh(it, with_for_update=True)
        if it.state not in (S.PENDING.value, S.WAITLISTED.value):
            raise conflict("not_cancelable", f"A {it.state.lower()} request cannot be canceled")
        was_pending = it.state == S.PENDING.value
        _transition(db, it, S.CANCELED, now, "sender_canceled")
        if was_pending:
            _promote_waitlist(db, it.to_user_id, now, cfg)
        db.commit()
        return it
    except Exception:
        db.rollback()
        raise


def reject_incoming_from(db: Session, viewer_id: uuid.UUID, sender_ids: list[uuid.UUID], reason: str, now: datetime, cfg: dict) -> None:
    """Viewer passed on people who had already chosen them. Caller holds viewer lock and commits."""
    if not sender_ids:
        return
    for it in db.scalars(
        select(Interest).where(
            Interest.to_user_id == viewer_id,
            Interest.from_user_id.in_(sender_ids),
            Interest.state.in_((S.PENDING.value, S.WAITLISTED.value)),
        ).with_for_update()
    ):
        _transition(db, it, S.REJECTED, now, reason)
    _promote_waitlist(db, viewer_id, now, cfg)


def close_between(db: Session, a: uuid.UUID, b: uuid.UUID, reason: str, now: datetime, cfg: dict) -> None:
    """Used on block: resolve any active interest in either direction. Caller holds locks."""
    for it in db.scalars(
        select(Interest).where(
            or_(and_(Interest.from_user_id == a, Interest.to_user_id == b), and_(Interest.from_user_id == b, Interest.to_user_id == a)),
            Interest.state.in_((S.PENDING.value, S.WAITLISTED.value)),
        ).with_for_update()
    ):
        _transition(db, it, S.CANCELED if it.from_user_id == a else S.REJECTED, now, reason)
    _promote_waitlist(db, a, now, cfg)
    _promote_waitlist(db, b, now, cfg)


def expire_due(db: Session, now: datetime | None = None, limit: int = 500) -> int:
    """Expire overdue PENDING/WAITLISTED interests and deliver waitlisted ones. Idempotent."""
    now = now or utcnow()
    cfg = get_config(db)
    due = db.execute(
        select(Interest.id, Interest.to_user_id)
        .where(Interest.state.in_((S.PENDING.value, S.WAITLISTED.value)), Interest.expires_at <= now)
        .limit(limit)
    ).all()
    count = 0
    for interest_id, to_user in due:
        try:
            lock_users(db, to_user)
            it = db.scalars(select(Interest).where(Interest.id == interest_id).with_for_update()).first()
            if it and it.state in (S.PENDING.value, S.WAITLISTED.value) and it.expires_at <= now:
                _transition(db, it, S.EXPIRED, now, "ttl")
                _promote_waitlist(db, to_user, now, cfg)
                count += 1
            db.commit()
        except Exception:
            db.rollback()
            raise
    return count


def incoming_pending(db: Session, user_id: uuid.UUID) -> list[Interest]:
    """Only delivered (PENDING) requests are visible to the recipient — never waitlisted ones."""
    now = utcnow()
    return db.scalars(
        select(Interest)
        .where(Interest.to_user_id == user_id, Interest.state == S.PENDING.value, Interest.expires_at > now)
        .order_by(Interest.delivered_at.desc())
    ).all()


def outgoing(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[Interest]:
    return db.scalars(
        select(Interest).where(Interest.from_user_id == user_id).order_by(Interest.created_at.desc()).limit(limit)
    ).all()


def bulk_mark_user_gone(db: Session, user_id: uuid.UUID, now: datetime) -> None:
    """Account deletion / ban: resolve all active interests involving the user and
    deliver anything that was waiting behind them. Caller commits."""
    cfg = get_config(db)
    affected = db.scalars(
        select(Interest)
        .where(or_(Interest.from_user_id == user_id, Interest.to_user_id == user_id), Interest.state.in_(ACTIVE_INTEREST_STATES))
        .with_for_update()
    ).all()
    recipients = set()
    for it in affected:
        _transition(db, it, S.EXPIRED, now, "account_unavailable")
        if it.to_user_id != user_id:
            recipients.add(it.to_user_id)
    db.flush()
    for rid in sorted(recipients):
        lock_users(db, rid)
        _promote_waitlist(db, rid, now, cfg)
