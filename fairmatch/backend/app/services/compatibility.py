"""Configurable weighted compatibility scoring.

Each component returns a value in [0, 1] or None when there is not enough voluntarily
provided information. Missing components are excluded from the weighted mean and lower
`confidence`. Scores are used internally for ranking only and are never sent to clients
as percentages; clients receive qualitative, explainable insights instead.
"""
from dataclasses import dataclass, field

from app.services.persona import Persona

INTENT_AFFINITY: dict[frozenset, float] = {
    frozenset({"long_term"}): 1.0,
    frozenset({"long_term", "long_term_open_short"}): 0.85,
    frozenset({"long_term_open_short"}): 0.9,
    frozenset({"long_term_open_short", "short_term_open_long"}): 0.75,
    frozenset({"short_term_open_long"}): 0.85,
    frozenset({"short_term_open_long", "short_term"}): 0.75,
    frozenset({"short_term"}): 0.9,
    frozenset({"friendship_first"}): 0.9,
    frozenset({"friendship_first", "long_term"}): 0.55,
    frozenset({"friendship_first", "long_term_open_short"}): 0.55,
    frozenset({"figuring_out"}): 0.7,
    frozenset({"long_term", "short_term"}): 0.0,
}

LIFESTYLE_KEYS = ("smoking", "drinking", "exercise", "kids_want", "diet", "pets", "sleep")
COMMUNICATION_KEYS = ("texting", "calls", "conflict", "affection", "planning")


@dataclass
class CompatibilityResult:
    score: float | None
    confidence: float
    components: dict[str, float | None]
    shared_interests: list[str] = field(default_factory=list)
    shared_values: list[str] = field(default_factory=list)
    possible_frictions: list[str] = field(default_factory=list)


def _jaccard(a: list[str], b: list[str]) -> float | None:
    sa, sb = {x.lower() for x in a}, {x.lower() for x in b}
    if not sa or not sb:
        return None
    return len(sa & sb) / len(sa | sb)


def relationship_goals(a: Persona, b: Persona) -> float | None:
    if not a.relationship_intent or not b.relationship_intent:
        return None
    key = frozenset({a.relationship_intent, b.relationship_intent})
    if key in INTENT_AFFINITY:
        return INTENT_AFFINITY[key]
    return 0.5 if "figuring_out" in key else 0.4


def _categorical_similarity(a: dict, b: dict, keys: tuple[str, ...]) -> tuple[float | None, list[str]]:
    scores, frictions = [], []
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            continue
        if va == vb:
            scores.append(1.0)
        elif "flexible" in (va, vb) or "open" in (va, vb):
            scores.append(0.7)
        else:
            scores.append(0.25)
            frictions.append(k)
    if not scores:
        return None, []
    return sum(scores) / len(scores), frictions


def values_lifestyle(a: Persona, b: Persona) -> tuple[float | None, list[str]]:
    v = _jaccard(a.values, b.values)
    life, frictions = _categorical_similarity(a.lifestyle, b.lifestyle, LIFESTYLE_KEYS)
    parts = [x for x in (v, life) if x is not None]
    if not parts:
        return None, []
    # Shared values count somewhat more than lifestyle overlap; overlap of 3+ values is already strong.
    if v is not None:
        parts[0] = min(1.0, v * 1.6)
    return sum(parts) / len(parts), frictions


def _range_fit(value: int, lo: int, hi: int) -> float:
    if hi <= lo:
        return 1.0
    centre, half = (lo + hi) / 2, (hi - lo) / 2
    return max(0.0, 1.0 - 0.5 * abs(value - centre) / half)


def mutual_preferences(a: Persona, b: Persona, distance_km: float | None) -> float:
    s = (_range_fit(b.age, a.age_min, a.age_max) + _range_fit(a.age, b.age_min, b.age_max)) / 2
    if distance_km is not None:
        limit = max(1, min(a.max_distance_km, b.max_distance_km))
        s = 0.7 * s + 0.3 * max(0.0, 1 - distance_km / limit)
    return s


def communication(a: Persona, b: Persona) -> tuple[float | None, list[str]]:
    return _categorical_similarity(a.communication, b.communication, COMMUNICATION_KEYS)


def score(a: Persona, b: Persona, weights: dict[str, float], distance_km: float | None = None) -> CompatibilityResult:
    vl, life_frictions = values_lifestyle(a, b)
    comm, comm_frictions = communication(a, b)
    components = {
        "relationship_goals": relationship_goals(a, b),
        "values_lifestyle": vl,
        "mutual_preferences": mutual_preferences(a, b, distance_km),
        "communication": comm,
        "shared_interests": _jaccard(a.interests, b.interests),
    }
    total_w = sum(weights.values()) or 1.0
    avail_w = sum(weights[k] for k, v in components.items() if v is not None and k in weights)
    confidence = avail_w / total_w
    if avail_w == 0:
        value = None
    else:
        value = sum(weights[k] * v for k, v in components.items() if v is not None and k in weights) / avail_w

    shared_interests = sorted({x.lower() for x in a.interests} & {x.lower() for x in b.interests})
    shared_values = sorted({x.lower() for x in a.values} & {x.lower() for x in b.values})
    frictions = []
    if components["relationship_goals"] is not None and components["relationship_goals"] < 0.6:
        frictions.append("relationship_goals")
    frictions += [f"lifestyle:{k}" for k in life_frictions] + [f"communication:{k}" for k in comm_frictions]
    return CompatibilityResult(value, confidence, components, shared_interests, shared_values, frictions)


FRICTION_TEXT = {
    "relationship_goals": "You may be looking for different kinds of relationships",
    "lifestyle:smoking": "Different views on smoking",
    "lifestyle:drinking": "Different drinking habits",
    "lifestyle:exercise": "Different activity levels",
    "lifestyle:kids_want": "Different plans around children",
    "lifestyle:diet": "Different diets",
    "lifestyle:pets": "Different feelings about pets",
    "lifestyle:sleep": "Different sleep rhythms",
    "communication:texting": "Different texting styles",
    "communication:calls": "Different preferences for calls",
    "communication:conflict": "Different ways of handling disagreements",
    "communication:affection": "Different ways of showing affection",
    "communication:planning": "Spontaneous vs. planner",
}


def public_insights(result: CompatibilityResult, min_confidence: float) -> dict:
    """Qualitative, honest insights safe to send to clients. No numeric score."""
    if result.confidence < min_confidence:
        return {
            "available": False,
            "explanation": "Not enough shared profile information yet to say much about compatibility. "
            "Profiles with more answers give better insights.",
            "shared_interests": result.shared_interests[:5],
            "shared_values": [],
            "considerations": [],
        }
    highlights = []
    if (result.components.get("relationship_goals") or 0) >= 0.85:
        highlights.append("Looking for a similar kind of relationship")
    if (result.components.get("communication") or 0) >= 0.8:
        highlights.append("Similar communication style")
    if result.shared_values:
        highlights.append("Shares values you care about")
    return {
        "available": True,
        "explanation": "Based only on what you both chose to share. This is not a prediction of relationship success.",
        "highlights": highlights,
        "shared_interests": result.shared_interests[:5],
        "shared_values": result.shared_values[:5],
        "considerations": [FRICTION_TEXT.get(f, f) for f in result.possible_frictions][:3],
    }
