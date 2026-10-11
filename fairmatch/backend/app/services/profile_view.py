"""Builds the client-facing view of another user's profile. Only public profile fields
are exposed; raw coordinates, email, DOB and internal scores never leave the server."""
from datetime import date

from app.models import User
from app.services import compatibility
from app.services.eligibility import distance_km
from app.services.geo import distance_bucket
from app.services.persona import Persona, age_on
from app.services.storage import storage

INTENT_LABELS = {
    "long_term": "Long-term relationship",
    "long_term_open_short": "Long-term, open to short",
    "short_term_open_long": "Short-term, open to long",
    "short_term": "Something casual",
    "friendship_first": "Friendship first",
    "figuring_out": "Still figuring it out",
}


def photo_urls(user: User) -> list[str]:
    st = storage()
    return [st.url(p.storage_key) for p in user.photos if p.moderation_status == "approved"]


def public_profile(viewer: Persona | None, user: User, today: date, weights: dict | None = None, min_conf: float = 0.5) -> dict:
    p = user.profile
    dist = None
    if viewer is not None and p.show_distance:
        from app.services.persona import persona_from

        dist = distance_km(viewer, persona_from(user, p, today))
    data = {
        "id": str(user.id),
        "first_name": p.first_name,
        "age": age_on(user.date_of_birth, today),
        "distance": distance_bucket(dist),
        "city": p.city_label,
        "gender": p.gender if p.show_gender else None,
        "bio": p.bio,
        "photos": photo_urls(user),
        "relationship_intent": p.relationship_intent,
        "relationship_intent_label": INTENT_LABELS.get(p.relationship_intent or "", None),
        "interests": list(p.interests or []),
        "values": list(p.values or []),
        "lifestyle": dict(p.lifestyle or {}),
        "prompts": list(p.prompts or []),
        "verified": user.verification_status == "verified",
        "is_demo": user.is_demo,
    }
    if viewer is not None and weights is not None:
        from app.services.persona import persona_from

        other = persona_from(user, p, today)
        result = compatibility.score(viewer, other, weights, distance_km(viewer, other))
        data["insights"] = compatibility.public_insights(result, min_conf)
    return data
