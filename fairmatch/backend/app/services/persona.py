"""Plain data view of a user used by the pure matching functions (no DB access)."""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Persona:
    id: uuid.UUID
    age: int
    gender: str
    interested_in: list[str]
    relationship_intent: str | None = None
    interests: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    lifestyle: dict = field(default_factory=dict)
    communication: dict = field(default_factory=dict)
    dealbreakers: dict = field(default_factory=dict)
    lat: float | None = None
    lon: float | None = None
    age_min: int = 18
    age_max: int = 99
    max_distance_km: int = 50
    status: str = "active"
    discoverable: bool = True
    completed: bool = True
    is_demo: bool = False
    last_active_at: datetime | None = None
    verified: bool = False


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def persona_from(user, profile, today: date) -> Persona:
    return Persona(
        id=user.id,
        age=age_on(user.date_of_birth, today),
        gender=profile.gender,
        interested_in=list(profile.interested_in or []),
        relationship_intent=profile.relationship_intent,
        interests=list(profile.interests or []),
        values=list(profile.values or []),
        lifestyle=dict(profile.lifestyle or {}),
        communication=dict(profile.communication or {}),
        dealbreakers=dict(profile.dealbreakers or {}),
        lat=profile.approx_lat,
        lon=profile.approx_lon,
        age_min=profile.age_min,
        age_max=profile.age_max,
        max_distance_km=profile.max_distance_km,
        status=user.status,
        discoverable=profile.discoverable,
        completed=profile.completed,
        is_demo=user.is_demo,
        last_active_at=user.last_active_at,
        verified=user.verification_status == "verified",
    )
