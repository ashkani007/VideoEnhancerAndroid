"""Reciprocal eligibility: both people must fit each other's hard preferences."""
from app.services.geo import haversine_km
from app.services.persona import Persona

# Relationship intents that are mutually incompatible as hard filters.
# Everything else is handled softly by compatibility scoring.
INTENT_HARD_CONFLICTS = {frozenset({"long_term", "short_term"})}


def _wants(seeker: Persona, other: Persona) -> bool:
    # "everyone" opts into all genders. Otherwise the other person's gender must be listed.
    prefs = set(seeker.interested_in)
    return "everyone" in prefs or other.gender in prefs


def _intent_ok(a: Persona, b: Persona) -> bool:
    if not a.relationship_intent or not b.relationship_intent:
        return True
    return frozenset({a.relationship_intent, b.relationship_intent}) not in INTENT_HARD_CONFLICTS


def _dealbreakers_ok(seeker: Persona, other: Persona) -> bool:
    db = seeker.dealbreakers or {}
    life = other.lifestyle or {}
    if db.get("no_smokers") and life.get("smoking") in ("regularly", "sometimes"):
        return False
    if db.get("must_want_kids") and life.get("kids_want") == "no":
        return False
    if db.get("must_not_want_kids") and life.get("kids_want") == "yes":
        return False
    if db.get("verified_only") and not other.verified:
        return False
    return True


def distance_km(a: Persona, b: Persona) -> float | None:
    if None in (a.lat, a.lon, b.lat, b.lon):
        return None
    return haversine_km(a.lat, a.lon, b.lat, b.lon)


def one_way_ok(seeker: Persona, other: Persona, dist: float | None) -> bool:
    if not (seeker.age_min <= other.age <= seeker.age_max):
        return False
    if not _wants(seeker, other):
        return False
    if dist is not None and dist > seeker.max_distance_km:
        return False
    return _dealbreakers_ok(seeker, other)


def is_mutually_eligible(a: Persona, b: Persona, blocked: bool = False) -> bool:
    """Pure check. `blocked` must be True if either user has blocked the other."""
    if a.id == b.id or blocked:
        return False
    for p in (a, b):
        if p.status != "active" or p.age < 18 or not p.completed:
            return False
    if not b.discoverable:
        return False
    if a.is_demo != b.is_demo:  # demo data never mixes with real accounts
        return False
    if not _intent_ok(a, b):
        return False
    dist = distance_km(a, b)
    return one_way_ok(a, b, dist) and one_way_ok(b, a, dist)
