"""AI, billing, safety, media and public-config endpoints."""
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.config import get_settings
from app.db import get_db
from app.deps import client_ip, current_user
from app.errors import AppError, forbidden, not_found
from app.models import Interest, PairCandidate, User
from app.schemas import BlockIn, PurchaseIn, RephraseIn, ReportIn
from app.security import verify_media_signature
from app.services import ai, billing, compatibility, safety
from app.services.app_config import get_config
from app.services.eligibility import distance_km
from app.services.entitlements import entitlements
from app.services.persona import persona_from
from app.services.profile_view import INTENT_LABELS, public_profile
from app.services.ratelimit import limiter
from app.services.storage import storage

router = APIRouter()


# ---------------------------------------------------------------- AI
def _require_ai(db: Session, user: User) -> dict:
    cfg = get_config(db)
    if not entitlements(db, cfg, user.id)["ai_assistant"]:
        raise forbidden("The AI assistant is part of Premium AI")
    if not (user.profile and user.profile.ai_processing_consent):
        raise AppError(403, "ai_consent_required", "Turn on AI processing in Privacy settings to use the assistant")
    limiter.enforce(f"ai:{user.id}", 30, 3600)
    return cfg


@router.post("/ai/insights/{user_id}", tags=["ai"])
def ai_insights(user_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cfg = _require_ai(db, user)
    from app.api.profile import can_view

    other = db.get(User, user_id)
    if other is None or other.profile is None or not can_view(db, user, user_id):
        raise not_found("Profile")
    today = utcnow().date()
    me_p, other_p = persona_from(user, user.profile, today), persona_from(other, other.profile, today)
    result = compatibility.score(me_p, other_p, cfg["matching"]["weights"], distance_km(me_p, other_p))
    me_view = public_profile(None, user, today)
    other_view = public_profile(None, other, today)
    if not other.profile.allow_ai_on_my_profile:
        out = ai.rule_based_insights(me_view, other_view, result)
        out["note"] = "This person has opted out of AI analysis, so these are simple rule-based suggestions."
        return out
    return ai.compatibility_insights(me_view, other_view, result)


@router.post("/ai/rephrase", tags=["ai"])
def ai_rephrase(body: RephraseIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _require_ai(db, user)
    return ai.rephrase(body.draft)


@router.get("/ai/reflection", tags=["ai"])
def ai_reflection(db: Session = Depends(get_db), user: User = Depends(current_user)):
    _require_ai(db, user)
    p = user.profile
    fields = [p.bio, p.interests, p.values, p.lifestyle, p.communication, p.prompts, p.relationship_intent]
    stats = {
        "selections": db.scalar(select(func.count()).select_from(Interest).where(Interest.from_user_id == user.id)),
        "passes": db.scalar(select(func.count()).select_from(PairCandidate).where(PairCandidate.viewer_id == user.id, PairCandidate.state == "PASSED")),
        "intent": INTENT_LABELS.get(p.relationship_intent or ""),
        "profile_completeness": round(sum(1 for f in fields if f) / len(fields), 2),
    }
    return ai.preference_reflection(stats)


# ---------------------------------------------------------------- Billing
@router.get("/billing/products", tags=["billing"])
def products(db: Session = Depends(get_db)):
    cfg = get_config(db)
    return {"products": [{"id": k, **v} for k, v in cfg["products"].items()], "tiers": cfg["tiers"]}


@router.post("/billing/verify", tags=["billing"])
def verify_purchase(body: PurchaseIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    limiter.enforce(f"billing:{user.id}", 20, 3600)
    return billing.verify_and_apply(db, user.id, body.product_id, body.purchase_token, client_ip(request))


@router.get("/billing/subscriptions", tags=["billing"])
def my_subscriptions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {
        "subscriptions": billing.subscription_summary(db, user.id),
        "cancellation_info": "Subscriptions are managed by Google Play. Cancel any time in Play Store → Payments & "
        "subscriptions; you keep access until the end of the paid period.",
    }


@router.post("/billing/rtdn", tags=["billing"], status_code=204)
async def google_rtdn(request: Request, token: str, db: Session = Depends(get_db)):
    """Google Play Real-time Developer Notifications via Pub/Sub push. Every notification is
    re-verified against the Play Developer API; the payload itself is never trusted."""
    import base64
    import hmac
    import json

    secret = get_settings().rtdn_shared_secret
    if not secret or not hmac.compare_digest(token, secret):
        raise forbidden("invalid token")
    envelope = await request.json()
    data = json.loads(base64.b64decode(envelope["message"]["data"]))
    sub = data.get("subscriptionNotification")
    if sub and sub.get("purchaseToken"):
        billing.refresh_from_notification(db, sub["purchaseToken"])


# ---------------------------------------------------------------- Safety
@router.post("/safety/block", tags=["safety"], status_code=204)
def block_user(body: BlockIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    safety.block(db, user.id, body.user_id)


@router.delete("/safety/block/{user_id}", tags=["safety"], status_code=204)
def unblock_user(user_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    safety.unblock(db, user.id, user_id)


@router.post("/safety/report", tags=["safety"], status_code=201)
def report_user(body: ReportIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    limiter.enforce(f"report:{user.id}", 20, 86400)
    r = safety.report(db, user.id, body.user_id, body.reason, body.details, body.block)
    return {"report_id": str(r.id), "message": "Thanks for telling us. Our team reviews every report."}


# ---------------------------------------------------------------- Media & config
@router.get("/media/{key:path}", tags=["media"])
def media(key: str, exp: int, sig: str):
    if exp < time.time() or not verify_media_signature(key, exp, sig):
        raise forbidden("Link expired")
    data = storage().get(key)
    if data is None:
        raise not_found("Media")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600"})


@router.get("/config/public", tags=["config"])
def public_config(db: Session = Depends(get_db)):
    cfg = get_config(db)
    return {
        "interest": cfg["interest"],
        "tiers": cfg["tiers"],
        "products": cfg["products"],
        "report_reasons": sorted(safety.REPORT_REASONS),
        "intents": INTENT_LABELS,
    }
