"""Entitlements are derived ONLY from server-verified purchase records."""
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.models import Boost, Subscription

TIER_RANK = {"free": 0, "plus": 1, "premium_ai": 2}
ENTITLED_STATUSES = ("active", "grace", "canceled")  # canceled = auto-renew off, still paid until expiry


def current_tier(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> str:
    now = now or utcnow()
    subs = db.scalars(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(ENTITLED_STATUSES),
            Subscription.expires_at > now,
        )
    ).all()
    best = "free"
    for s in subs:
        if TIER_RANK.get(s.tier, 0) > TIER_RANK[best]:
            best = s.tier
    return best


def entitlements(db: Session, cfg: dict, user_id: uuid.UUID, now: datetime | None = None) -> dict:
    tier = current_tier(db, user_id, now)
    return {"tier": tier, **cfg["tiers"][tier]}


def active_boost(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> Boost | None:
    now = now or utcnow()
    return db.scalars(
        select(Boost).where(Boost.user_id == user_id, Boost.starts_at <= now, Boost.ends_at > now)
    ).first()


def boosted_user_ids(db: Session, user_ids: list[uuid.UUID], now: datetime) -> set[uuid.UUID]:
    if not user_ids:
        return set()
    rows = db.scalars(
        select(Boost.user_id).where(Boost.user_id.in_(user_ids), Boost.starts_at <= now, Boost.ends_at > now)
    )
    return set(rows)
