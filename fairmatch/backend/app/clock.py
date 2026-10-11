from datetime import datetime, timezone


def utcnow() -> datetime:
    """Single time source so tests can freeze/advance time."""
    return datetime.now(timezone.utc)
