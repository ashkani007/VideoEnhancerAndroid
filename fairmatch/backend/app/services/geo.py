"""Location privacy helpers. Coordinates are coarsened before storage and distances are bucketed."""
import math

COARSEN_DEGREES = 0.02  # ~2 km latitude grid


def coarsen(lat: float, lon: float) -> tuple[float, float]:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("invalid coordinates")
    q = COARSEN_DEGREES
    return round(round(lat / q) * q, 4), round(round(lon / q) * q, 4)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_bucket(km: float | None) -> str | None:
    """Human-friendly approximate distance; never precise enough to trilaterate."""
    if km is None:
        return None
    if km < 5:
        return "Less than 5 km away"
    if km < 100:
        return f"About {int(5 * round(km / 5))} km away"
    return "100+ km away"
