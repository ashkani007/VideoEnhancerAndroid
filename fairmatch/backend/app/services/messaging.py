"""Messaging between matched users. Transport is TLS + server-side authorization;
messages are NOT end-to-end encrypted."""
import re
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.errors import AppError, bad_request, conflict, not_found
from app.models import Match, Message, Profile
from app.services.app_config import get_config
from app.services.push import notify_user
from app.services.ratelimit import limiter
from app.services.realtime import hub
from app.services.safety import flag_suspicious

LINK_RE = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|io|ru|xyz|top|link|me)\b)", re.I)


def get_match_for(db: Session, user_id: uuid.UUID, match_id: uuid.UUID) -> Match:
    m = db.get(Match, match_id)
    if m is None or not m.includes(user_id):
        raise not_found("Conversation")
    return m


def serialize(msg: Message, viewer_id: uuid.UUID, share_read: bool) -> dict:
    return {
        "id": msg.id,
        "match_id": str(msg.match_id),
        "sender_id": str(msg.sender_id) if msg.sender_id else None,
        "client_message_id": msg.client_message_id,
        "body": "[message removed]" if msg.deleted else msg.body,
        "created_at": msg.created_at.isoformat(),
        "status": _status(msg, viewer_id, share_read),
    }


def _status(msg: Message, viewer_id: uuid.UUID, share_read: bool) -> str:
    if msg.sender_id != viewer_id:
        return "received"
    if msg.read_at and share_read:
        return "read"
    if msg.delivered_at:
        return "delivered"
    return "sent"


def read_receipts_shared(db: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    """Reciprocal: read receipts are shown only if both people have them enabled."""
    vals = db.scalars(select(Profile.read_receipts).where(Profile.user_id.in_([a, b]))).all()
    return len(vals) == 2 and all(vals)


def send(db: Session, sender_id: uuid.UUID, match_id: uuid.UUID, body: str, client_message_id: str) -> tuple[Message, bool]:
    cfg = get_config(db)["safety"]
    body = (body or "").strip()
    if not body:
        raise bad_request("empty", "Message cannot be empty")
    if len(body) > cfg["max_message_length"]:
        raise bad_request("too_long", "Message is too long")
    if not client_message_id or len(client_message_id) > 64:
        raise bad_request("client_message_id_required", "client_message_id is required")

    # Idempotent retry (offline resend) returns the stored message.
    prior = db.scalars(
        select(Message).where(Message.sender_id == sender_id, Message.client_message_id == client_message_id)
    ).first()
    if prior:
        return prior, False

    m = get_match_for(db, sender_id, match_id)
    if m.state != "active":
        raise conflict("match_closed", "This conversation has ended")
    limiter.enforce(f"msg:{sender_id}", cfg["messages_per_minute"], 60)

    sent_before = db.scalar(
        select(func.count()).select_from(Message).where(Message.match_id == match_id, Message.sender_id == sender_id)
    )
    if cfg["block_links_in_first_message"] and sent_before == 0 and LINK_RE.search(body):
        flag_suspicious(db, sender_id, 2, "link_in_first_message")
        db.commit()
        raise AppError(422, "links_not_allowed_yet", "Links can't be sent in a first message. Get to know each other first.")

    # Spam heuristic: identical text fanned out to many conversations in a short time.
    window = utcnow() - timedelta(minutes=10)
    fanout = db.scalar(
        select(func.count(func.distinct(Message.match_id))).where(
            Message.sender_id == sender_id, Message.body == body, Message.created_at >= window
        )
    )
    if fanout >= cfg["duplicate_message_fanout_limit"]:
        flag_suspicious(db, sender_id, 5, "duplicate_fanout")
        db.commit()
        raise AppError(429, "spam_suspected", "This looks like a copy-pasted message. Try writing something personal.")

    now = utcnow()
    recipient = m.other(sender_id)
    msg = Message(match_id=match_id, sender_id=sender_id, client_message_id=client_message_id, body=body, created_at=now)
    if hub.online(recipient):
        msg.delivered_at = now
    db.add(msg)
    m.last_message_at = now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.scalars(
            select(Message).where(Message.sender_id == sender_id, Message.client_message_id == client_message_id)
        ).one()
        return prior, False

    share = read_receipts_shared(db, sender_id, recipient)
    hub.publish(recipient, {"type": "message", "message": serialize(msg, recipient, share)})
    if msg.delivered_at is None:
        name = db.scalar(select(Profile.first_name).where(Profile.user_id == sender_id)) or "Your match"
        notify_user(db, recipient, f"New message from {name}", "Open FairMatch to read it.", {"type": "message", "match_id": str(match_id)})
    return msg, True


def list_messages(db: Session, user_id: uuid.UUID, match_id: uuid.UUID, before_id: int | None, after_id: int | None, limit: int) -> list[Message]:
    get_match_for(db, user_id, match_id)
    limit = max(1, min(limit, 100))
    q = select(Message).where(Message.match_id == match_id)
    if after_id is not None:  # offline recovery: everything newer than what the client has
        q = q.where(Message.id > after_id).order_by(Message.id.asc()).limit(limit)
        rows = db.scalars(q).all()
    else:
        if before_id is not None:
            q = q.where(Message.id < before_id)
        rows = list(reversed(db.scalars(q.order_by(Message.id.desc()).limit(limit)).all()))
    # Fetching = delivered to this device.
    now = utcnow()
    changed = [r for r in rows if r.sender_id != user_id and r.delivered_at is None]
    for r in changed:
        r.delivered_at = now
    if changed:
        db.commit()
    return rows


def mark_read(db: Session, user_id: uuid.UUID, match_id: uuid.UUID, up_to_id: int) -> int:
    m = get_match_for(db, user_id, match_id)
    now = utcnow()
    rows = db.scalars(
        select(Message).where(
            Message.match_id == match_id, Message.sender_id != user_id, Message.id <= up_to_id, Message.read_at.is_(None)
        )
    ).all()
    for r in rows:
        r.read_at = now
        r.delivered_at = r.delivered_at or now
    db.commit()
    other = m.other(user_id)
    if rows and read_receipts_shared(db, user_id, other):
        hub.publish(other, {"type": "read", "match_id": str(match_id), "up_to_id": up_to_id})
    return len(rows)


def typing(db: Session, user_id: uuid.UUID, match_id: uuid.UUID) -> None:
    m = get_match_for(db, user_id, match_id)
    if m.state == "active":
        hub.publish(m.other(user_id), {"type": "typing", "match_id": str(match_id)})
