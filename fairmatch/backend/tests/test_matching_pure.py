"""Pure-function tests: eligibility, compatibility, fairness."""
import random
import uuid

from app.services import compatibility, fairness
from app.services.app_config import DEFAULTS
from app.services.eligibility import is_mutually_eligible
from app.services.persona import Persona

W = DEFAULTS["matching"]["weights"]


def P(**kw):
    base = dict(id=uuid.uuid4(), age=30, gender="woman", interested_in=["man"], relationship_intent="long_term",
                interests=["hiking", "coffee"], values=["honesty"], lat=52.37, lon=4.89)
    base.update(kw)
    return Persona(**base)


def test_reciprocal_gender_preferences():
    a = P(gender="woman", interested_in=["man"])
    b = P(gender="man", interested_in=["woman"])
    assert is_mutually_eligible(a, b)
    c = P(gender="man", interested_in=["man"])  # c is not interested in a
    assert not is_mutually_eligible(a, c)
    assert not is_mutually_eligible(c, a)


def test_everyone_preference_and_nonbinary():
    a = P(gender="nonbinary", interested_in=["everyone"])
    b = P(gender="woman", interested_in=["nonbinary", "woman"])
    assert is_mutually_eligible(a, b)


def test_age_ranges_are_reciprocal():
    a = P(age=40, interested_in=["man"], age_min=35, age_max=45)
    b = P(age=30, gender="man", interested_in=["woman"])
    assert not is_mutually_eligible(a, b)
    b2 = P(age=38, gender="man", interested_in=["woman"], age_min=20, age_max=35)
    assert not is_mutually_eligible(a, b2)  # a is too old for b2
    b3 = P(age=38, gender="man", interested_in=["woman"], age_min=30, age_max=45)
    assert is_mutually_eligible(a, b3)


def test_distance_limits_both_ways():
    a = P(max_distance_km=10)
    b = P(gender="man", interested_in=["woman"], lat=52.09, lon=5.12, max_distance_km=200)  # ~35 km away
    assert not is_mutually_eligible(a, b)
    a.max_distance_km = 50
    assert is_mutually_eligible(a, b)


def test_blocks_status_minors_demo_and_intent_conflicts():
    a = P()
    b = P(gender="man", interested_in=["woman"])
    assert not is_mutually_eligible(a, b, blocked=True)
    assert not is_mutually_eligible(a, P(gender="man", interested_in=["woman"], status="suspended"))
    assert not is_mutually_eligible(a, P(gender="man", interested_in=["woman"], age=17))
    assert not is_mutually_eligible(a, P(gender="man", interested_in=["woman"], is_demo=True))
    assert not is_mutually_eligible(a, P(gender="man", interested_in=["woman"], relationship_intent="short_term"))
    assert not is_mutually_eligible(a, P(gender="man", interested_in=["woman"], discoverable=False))


def test_dealbreakers():
    a = P(dealbreakers={"no_smokers": True})
    smoker = P(gender="man", interested_in=["woman"], lifestyle={"smoking": "regularly"})
    assert not is_mutually_eligible(a, smoker)


def test_compatibility_weights_and_confidence():
    a = P(values=["honesty", "family"], lifestyle={"smoking": "never"}, communication={"texting": "often"})
    b = P(gender="man", interested_in=["woman"], values=["honesty", "family"], lifestyle={"smoking": "never"},
          communication={"texting": "often"}, interests=["hiking", "coffee"])
    r = compatibility.score(a, b, W, 0.0)
    assert r.confidence == 1.0
    assert 0.8 < r.score <= 1.0
    assert r.shared_values == ["family", "honesty"]

    # Incompatible goals pull the score down.
    c = P(gender="man", interested_in=["woman"], relationship_intent="friendship_first", values=["adventure"],
          lifestyle={"smoking": "regularly"}, communication={"texting": "rarely"}, interests=["gaming"])
    rc = compatibility.score(a, c, W, 0.0)
    assert rc.score < r.score
    assert "relationship_goals" in rc.possible_frictions


def test_missing_data_lowers_confidence_and_hides_insights():
    a = P(relationship_intent=None, values=[], interests=[], lifestyle={}, communication={})
    b = P(gender="man", interested_in=["woman"], relationship_intent=None, values=[], interests=[])
    r = compatibility.score(a, b, W, None)
    assert r.confidence == W["mutual_preferences"] / sum(W.values())
    out = compatibility.public_insights(r, 0.5)
    assert out["available"] is False
    assert "Not enough" in out["explanation"]
    assert "score" not in out  # never a numeric score


def test_weights_are_configurable():
    a, b = P(), P(gender="man", interested_in=["woman"], interests=["chess"])
    only_interests = {k: 0.0 for k in W} | {"shared_interests": 1.0}
    r = compatibility.score(a, b, only_interests, 0.0)
    assert r.score == 0.0


def test_gini():
    assert fairness.gini([5, 5, 5, 5]) == 0.0
    assert fairness.gini([0, 0, 0, 10]) > 0.7


def test_exposure_bonus_prefers_underexposed():
    assert fairness.blended_score(0.6, 0, 10, 0.3) > fairness.blended_score(0.6, 50, 10, 0.3)


def test_boost_cap():
    cap = 0.10
    allowed, boosted, total = 0, 0, 0
    for _ in range(100):
        if fairness.boost_slot_allowed(boosted, total, cap):
            boosted += 1
        total += 2
    assert boosted / total <= cap + 0.01


def test_fair_exposure_reduces_inequality_in_simulation():
    """Simulate pair generation over a pool where a few profiles score much higher.
    With fairness on, impressions are spread more evenly than with lambda=0."""
    from app.services.pairing import ScoredCandidate, choose_pair

    def simulate(lam: float) -> float:
        rng = random.Random(7)
        n = 40
        compat = [0.95 if i < 4 else 0.55 + 0.1 * rng.random() for i in range(n)]
        imp = [0] * n
        cfg = {"matching": dict(DEFAULTS["matching"], fairness_lambda=lam)}
        for _ in range(600):
            med = fairness.pool_median(imp)
            scored = []
            for i in range(n):
                sc = ScoredCandidate(i, P(interests=[str(i)]), compat[i], fairness.blended_score(compat[i], imp[i], med, lam), False, False)
                scored.append(sc)
            scored.sort(key=lambda c: c.rank, reverse=True)
            for c in choose_pair(scored, cfg, rng):
                imp[c.user] += 1
        return fairness.gini(imp)

    assert simulate(0.3) < simulate(0.0) - 0.15
