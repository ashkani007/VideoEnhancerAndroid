"""Server-configurable product values.

Defaults live here; operators override individual top-level keys via the
`app_config` table (admin API). Every value the product spec calls
"configurable" (quotas, capacities, weights, prices, entitlements) is read from here.
"""
import copy
import threading
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppConfigEntry

DEFAULTS: dict[str, Any] = {
    "interest": {
        "max_incoming_pending": 2,
        "pending_ttl_hours": 48,
        "waitlist_ttl_hours": 168,
    },
    "matching": {
        # Experimental weights, NOT scientifically validated constants.
        "weights": {
            "relationship_goals": 0.30,
            "values_lifestyle": 0.25,
            "mutual_preferences": 0.20,
            "communication": 0.15,
            "shared_interests": 0.10,
        },
        "min_confidence_for_insights": 0.5,
        "fairness_lambda": 0.30,  # share of ranking driven by exposure deficit
        "exposure_window_days": 7,
        "diversity_penalty": 0.25,
        "full_inbox_penalty": 0.5,  # multiplier when a candidate's pending inbox is full
        "incoming_interest_bonus": 0.15,
        "boost_bonus": 0.20,
        "boost_inventory_cap": 0.10,  # max share of slots that may be boost-promoted
        "repeat_cooldown_days": 30,  # do not re-show passed candidates within this window
        "candidate_pool_limit": 400,
        "top_k_sampling": 8,
    },
    "tiers": {
        "free": {
            "daily_positive_selections": 5,
            "see_incoming_likes": False,
            "advanced_filters": False,
            "profile_analytics": False,
            "ai_assistant": False,
        },
        "plus": {
            "daily_positive_selections": 15,
            "see_incoming_likes": True,
            "advanced_filters": True,
            "profile_analytics": True,
            "ai_assistant": False,
        },
        "premium_ai": {
            "daily_positive_selections": 15,
            "see_incoming_likes": True,
            "advanced_filters": True,
            "profile_analytics": True,
            "ai_assistant": True,
        },
    },
    "products": {
        "fairmatch_plus_monthly": {"kind": "subscription", "tier": "plus", "price": "9.99", "currency": "EUR", "period": "P1M"},
        "fairmatch_premium_ai_monthly": {
            "kind": "subscription",
            "tier": "premium_ai",
            "price": "19.99",
            "currency": "EUR",
            "period": "P1M",
        },
        "fairmatch_boost_30m": {"kind": "consumable", "boost_minutes": 30, "price": "2.99", "currency": "EUR"},
    },
    "safety": {
        "auto_review_distinct_reporters": 3,
        "messages_per_minute": 20,
        "max_message_length": 2000,
        "block_links_in_first_message": True,
        "duplicate_message_fanout_limit": 4,
        "deletion_grace_days": 7,
    },
}

_cache: dict[str, Any] | None = None
_cache_at = 0.0
_lock = threading.Lock()
CACHE_SECONDS = 30


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def get_config(db: Session) -> dict[str, Any]:
    global _cache, _cache_at
    with _lock:
        if _cache is not None and time.monotonic() - _cache_at < CACHE_SECONDS:
            return _cache
    overrides = {e.key: e.value for e in db.scalars(select(AppConfigEntry))}
    merged = _merge(DEFAULTS, overrides)
    with _lock:
        _cache, _cache_at = merged, time.monotonic()
    return merged


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def set_override(db: Session, key: str, value: dict, actor_id=None) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    entry = db.get(AppConfigEntry, key)
    if entry is None:
        entry = AppConfigEntry(key=key, value=value, updated_by=actor_id)
        db.add(entry)
    else:
        entry.value = value
        entry.updated_by = actor_id
    db.flush()
    invalidate_cache()
