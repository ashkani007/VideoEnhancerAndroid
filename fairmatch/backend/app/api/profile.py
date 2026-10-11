import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.db import get_db
from app.deps import client_ip, current_user
from app.errors import bad_request, forbidden, not_found
from app.models import Block, Consent, DeviceToken, Interest, Match, PairCandidate, Photo, Profile, User
from app.schemas import ConsentIn, DeviceIn, ProfileIn
from app.services import entitlements as ent
from app.services import interests as interest_svc
from app.services import privacy
from app.services.app_config import get_config
from app.services.audit import audit
from app.services.geo import coarsen
from app.services.persona import age_on, persona_from
from app.services.profile_view import photo_urls, public_profile
from app.services.ratelimit import limiter
from app.services.storage import new_photo_key, sanitize_image, storage

router = APIRouter(tags=["profile"])
MAX_PHOTOS = 6


def _is_complete(user: User, p: Profile) -> bool:
    has_photo = any(ph.moderation_status != "rejected" for ph in user.photos) or user.is_demo
    return bool(p.first_name and p.gender and p.interested_in and p.relationship_intent and p.approx_lat is not None and has_photo)


def my_profile_dict(db: Session, user: User) -> dict:
    p = user.profile
    cfg = get_config(db)
    remaining, limit = interest_svc.remaining_selections(db, user.id)
    out = {
        "id": str(user.id),
        "email": user.email,
        "age": age_on(user.date_of_birth, utcnow().date()),
        "status": user.status,
        "role": user.role,
        "verification_status": user.verification_status,
        "age_assurance": user.age_assurance,
        "is_demo": user.is_demo,
        "entitlements": ent.entitlements(db, cfg, user.id),
        "selections": {"remaining": remaining, "daily_limit": limit},
        "boost_active_until": (b.ends_at.isoformat() if (b := ent.active_boost(db, user.id)) else None),
        "profile": None,
    }
    if p is not None:
        out["profile"] = {
            "first_name": p.first_name, "bio": p.bio, "gender": p.gender, "show_gender": p.show_gender,
            "interested_in": p.interested_in, "relationship_intent": p.relationship_intent,
            "interests": p.interests, "values": p.values, "lifestyle": p.lifestyle, "communication": p.communication,
            "dealbreakers": p.dealbreakers, "prompts": p.prompts, "city_label": p.city_label,
            "has_location": p.approx_lat is not None, "age_min": p.age_min, "age_max": p.age_max,
            "max_distance_km": p.max_distance_km, "show_distance": p.show_distance, "read_receipts": p.read_receipts,
            "ai_processing_consent": p.ai_processing_consent, "allow_ai_on_my_profile": p.allow_ai_on_my_profile,
            "discoverable": p.discoverable, "completed": p.completed,
            "photos": [{"id": str(ph.id), "url": u} for ph, u in zip([x for x in user.photos if x.moderation_status == "approved"], photo_urls(user))],
        }
    return out


@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return my_profile_dict(db, user)


@router.patch("/me/profile")
def update_profile(body: ProfileIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    data = body.model_dump(exclude_unset=True)
    p = user.profile
    if p is None:
        if not data.get("first_name") or not data.get("gender"):
            raise bad_request("missing_fields", "first_name and gender are required to create a profile")
        p = Profile(user_id=user.id, first_name=data["first_name"], gender=data["gender"], interested_in=[], interests=[], values=[],
                    lifestyle={}, communication={}, dealbreakers={}, prompts=[], bio="", show_gender=True, age_min=18,
                    age_max=99, max_distance_km=50, show_distance=True, read_receipts=True, ai_processing_consent=False,
                    allow_ai_on_my_profile=True, discoverable=True, completed=False)
        db.add(p)
        user.profile = p
    lat, lon = data.pop("latitude", None), data.pop("longitude", None)
    if (lat is None) != (lon is None):
        raise bad_request("invalid_location", "Provide both latitude and longitude")
    if lat is not None:
        p.approx_lat, p.approx_lon = coarsen(lat, lon)  # raw coordinates are never stored
    if "prompts" in data and data["prompts"] is not None:
        data["prompts"] = [dict(x) for x in data["prompts"]]
    if "ai_processing_consent" in data and data["ai_processing_consent"] != p.ai_processing_consent:
        db.add(Consent(user_id=user.id, kind="ai_processing", granted=bool(data["ai_processing_consent"])))
    for k, v in data.items():
        if v is not None:
            setattr(p, k, v)
    if p.age_max < p.age_min:
        raise bad_request("invalid_age_range", "Maximum age must be at least the minimum age")
    p.completed = _is_complete(user, p)
    db.commit()
    db.refresh(user)
    return my_profile_dict(db, user)


@router.post("/me/photos", status_code=201)
async def upload_photo(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    limiter.enforce(f"photo:{user.id}", 20, 3600)
    if len(user.photos) >= MAX_PHOTOS:
        raise bad_request("too_many_photos", f"You can add up to {MAX_PHOTOS} photos")
    raw = await file.read(8 * 1024 * 1024 + 1)
    clean = sanitize_image(raw)
    key = new_photo_key(user.id)
    storage().put(key, clean, "image/jpeg")
    # Automated moderation hook would set "pending" here; approved by default in this build.
    ph = Photo(user_id=user.id, storage_key=key, position=len(user.photos), moderation_status="approved")
    db.add(ph)
    db.flush()
    db.refresh(user)
    if user.profile:
        user.profile.completed = _is_complete(user, user.profile)
    db.commit()
    return {"id": str(ph.id), "url": storage().url(key)}


@router.delete("/me/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ph = db.get(Photo, photo_id)
    if ph is None or ph.user_id != user.id:
        raise not_found("Photo")
    storage().delete(ph.storage_key)
    db.delete(ph)
    db.flush()
    db.refresh(user)
    for i, x in enumerate(user.photos):
        x.position = i
    if user.profile:
        user.profile.completed = _is_complete(user, user.profile)
    db.commit()


@router.put("/me/photos/order")
def reorder_photos(ids: list[uuid.UUID], db: Session = Depends(get_db), user: User = Depends(current_user)):
    mine = {ph.id: ph for ph in user.photos}
    if set(ids) != set(mine):
        raise bad_request("invalid_order", "Provide every photo id exactly once")
    for i, pid in enumerate(ids):
        mine[pid].position = i
    db.commit()
    return {"ok": True}


@router.post("/me/consents")
def set_consent(body: ConsentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.add(Consent(user_id=user.id, kind=body.kind, granted=body.granted))
    if body.kind == "ai_processing" and user.profile:
        user.profile.ai_processing_consent = body.granted
    db.commit()
    return {"ok": True}


@router.post("/me/devices", status_code=204)
def register_device(body: DeviceIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    existing = db.get(DeviceToken, body.token)
    if existing:
        existing.user_id = user.id
    else:
        db.add(DeviceToken(token=body.token, user_id=user.id, platform=body.platform))
    db.commit()


@router.get("/me/export")
def export(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    limiter.enforce(f"export:{user.id}", 5, 86400)
    audit(db, "privacy.export", user.id, "user", user.id, ip=client_ip(request))
    db.commit()
    return JSONResponse(privacy.export_user_data(db, user.id), headers={"Content-Disposition": "attachment; filename=fairmatch-export.json"})


@router.delete("/me", status_code=202)
def delete_account(db: Session = Depends(get_db), user: User = Depends(current_user)):
    privacy.request_deletion(db, user)
    return {"status": "pending_deletion", "grace_days": get_config(db)["safety"]["deletion_grace_days"]}


def can_view(db: Session, viewer: User, target_id: uuid.UUID) -> bool:
    """Profiles are visible only within an existing relationship context: shown in a pair,
    matched, or an interest exists between the two. Never when either blocked the other."""
    blocked = db.scalar(
        select(func.count()).select_from(Block).where(
            or_(and_(Block.blocker_id == viewer.id, Block.blocked_id == target_id),
                and_(Block.blocker_id == target_id, Block.blocked_id == viewer.id))
        )
    )
    if blocked:
        return False
    since = utcnow() - timedelta(days=14)
    shown = db.scalar(
        select(func.count()).select_from(PairCandidate).where(
            PairCandidate.viewer_id == viewer.id, PairCandidate.candidate_id == target_id, PairCandidate.created_at >= since
        )
    )
    if shown:
        return True
    low, high = sorted((viewer.id, target_id))
    if db.scalar(select(func.count()).select_from(Match).where(Match.user_low_id == low, Match.user_high_id == high)):
        return True
    if db.scalar(select(func.count()).select_from(Interest).where(Interest.from_user_id == viewer.id, Interest.to_user_id == target_id)):
        return True
    cfg = get_config(db)
    if ent.entitlements(db, cfg, viewer.id)["see_incoming_likes"]:
        return bool(db.scalar(select(func.count()).select_from(Interest).where(
            Interest.from_user_id == target_id, Interest.to_user_id == viewer.id, Interest.state == "PENDING")))
    return False


@router.get("/users/{user_id}")
def view_profile(user_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    target = db.get(User, user_id)
    if target is None or target.profile is None or target.status != "active" or not can_view(db, user, user_id):
        raise not_found("Profile")
    if user.profile is None:
        raise forbidden("Create your profile first")
    cfg = get_config(db)
    today = utcnow().date()
    return public_profile(persona_from(user, user.profile, today), target, today,
                          cfg["matching"]["weights"], cfg["matching"]["min_confidence_for_insights"])
