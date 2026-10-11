"""Fair exposure allocation and monitoring.

Ranking never uses how many likes someone already received (avoids popularity feedback
loops). Instead, candidates with fewer recent impressions receive an exposure-deficit
bonus, blended with compatibility via `fairness_lambda`.
"""
from statistics import median


def exposure_bonus(impressions: int, pool_median: float) -> float:
    """1.0 for never-shown candidates, decaying as impressions exceed the pool median."""
    return 1.0 / (1.0 + impressions / (pool_median + 1.0))


def blended_score(compat: float, impressions: int, pool_median: float, lam: float) -> float:
    return (1 - lam) * compat + lam * exposure_bonus(impressions, pool_median)


def pool_median(impressions: list[int]) -> float:
    return float(median(impressions)) if impressions else 0.0


def gini(values: list[float]) -> float:
    """Gini coefficient of exposure (0 = perfectly equal, 1 = maximally unequal)."""
    vals = sorted(v for v in values if v >= 0)
    n = len(vals)
    if n == 0 or sum(vals) == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * cum) / (n * sum(vals)) - (n + 1) / n


def exposure_report(impressions: list[int]) -> dict:
    n = len(impressions)
    if n == 0:
        return {"users": 0, "gini": 0.0, "top_decile_share": 0.0, "zero_exposure_share": 0.0, "median": 0}
    s = sorted(impressions, reverse=True)
    total = sum(s) or 1
    top = s[: max(1, n // 10)]
    return {
        "users": n,
        "gini": round(gini(impressions), 4),
        "top_decile_share": round(sum(top) / total, 4),
        "zero_exposure_share": round(sum(1 for x in impressions if x == 0) / n, 4),
        "median": pool_median(impressions),
    }


def boost_slot_allowed(boosted_today: int, total_slots_today: int, cap: float) -> bool:
    """Boosted promotions may fill at most `cap` of a viewer's slots (counting the new pair)."""
    return (boosted_today + 1) <= cap * (total_slots_today + 2)
