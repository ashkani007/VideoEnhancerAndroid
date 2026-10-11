import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.db import get_db
from app.deps import current_user
from app.errors import forbidden
from app.models import Interest, Match, PairCandidate, User
from app.schemas import RespondIn, SelectIn
from app.services import interests as svc
from app.services import pairing
from app.services.app_config import get_config
from app.services.entitlements import entitlements
from app.services.persona import persona_from
from app.services.profile_view import public_profile

router = APIRouter(tags=["discover"])

STATE_COPY = {
    "WAITLISTED": "Waiting in line — they'll see it when they have room",
    "PENDING": "Delivered — waiting for their answer",
    "MATCHED": "Matched",
    "REJECTED": "Not this time",
    "EXPIRED": "Expired",
    "CANCELED": "Canceled",
}


def _pair_out(db: Session, viewer: User, pair) -> dict:
    cfg = get_config(db)
    today = utcnow().date()
    vp = persona_from(viewer, viewer.profile, today)
    cards = []
    for c in pair.candidates:
        u = db.get(User, c.candidate_id)
        card = public_profile(vp, u, today, cfg["matching"]["weights"], cfg["matching"]["min_confidence_for_insights"])
        card["promoted"] = c.boosted  # disclosed to users: paid visibility is labelled
        cards.append(card)
    remaining, limit = svc.remaining_selections(db, viewer.id)
    return {"pair_id": str(pair.id), "candidates": cards, "complete_pair": len(cards) == 2,
            "selections": {"remaining": remaining, "daily_limit": limit}}


@router.get("/discover/pair")
def get_pair(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.status != "active":
        raise forbidden("Your account is under review")
    pair = pairing.get_or_create_pair(db, user.id)
    if pair is None:
        remaining, limit = svc.remaining_selections(db, user.id)
        return {
            "pair_id": None, "candidates": [], "complete_pair": False,
            "empty_reason": "No new people match your preferences right now. Widening your distance or age range, "
            "or checking back later, can help. We never show made-up profiles.",
            "selections": {"remaining": remaining, "daily_limit": limit},
        }
    return _pair_out(db, user, pair)


@router.post("/discover/select")
def select_candidate(body: SelectIn, idempotency_key: str = Header(alias="Idempotency-Key"),
                     db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.status != "active":
        raise forbidden("Your account is under review")
    res = svc.select_candidate(db, user.id, body.pair_id, body.candidate_id, idempotency_key)
    remaining, limit = svc.remaining_selections(db, user.id)
    return {
        "interest_id": str(res.interest.id),
        "state": res.interest.state,
        "status_text": STATE_COPY.get(res.interest.state, res.interest.state),
        "matched": res.match is not None,
        "match_id": str(res.match.id) if res.match else None,
        "selections": {"remaining": remaining, "daily_limit": limit},
    }


@router.post("/discover/pass/{pair_id}", status_code=204)
def pass_pair(pair_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    pairing.pass_pair(db, user.id, pair_id)


def _interest_out(db: Session, viewer: User, it: Interest, other_id: uuid.UUID, include_profile: bool) -> dict:
    cfg = get_config(db)
    today = utcnow().date()
    out = {
        "id": str(it.id), "state": it.state, "status_text": STATE_COPY.get(it.state, it.state),
        "created_at": it.created_at.isoformat(), "expires_at": it.expires_at.isoformat() if it.expires_at else None,
    }
    if include_profile:
        u = db.get(User, other_id)
        if u and u.profile and u.status == "active":
            out["profile"] = public_profile(persona_from(viewer, viewer.profile, today), u, today,
                                            cfg["matching"]["weights"], cfg["matching"]["min_confidence_for_insights"])
    return out


@router.get("/likes")
def likes(db: Session = Depends(get_db), user: User = Depends(current_user)):
    cfg = get_config(db)
    ents = entitlements(db, cfg, user.id)
    incoming = svc.incoming_pending(db, user.id)
    out = {
        "incoming_count": len(incoming),
        "can_see_incoming": ents["see_incoming_likes"],
        "incoming": [],
        "incoming_note": None,
        "outgoing": [_interest_out(db, user, it, it.to_user_id, True) for it in svc.outgoing(db, user.id)],
    }
    if ents["see_incoming_likes"]:
        out["incoming"] = [_interest_out(db, user, it, it.from_user_id, True) for it in incoming]
    elif incoming:
        out["incoming_note"] = ("People who chose you are shown in your Discover pairs first, so you can "
                                "choose them back for free. Plus lets you see and answer them here directly.")
    return out


@router.post("/likes/{interest_id}/respond")
def respond(interest_id: uuid.UUID, body: RespondIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cfg = get_config(db)
    if not entitlements(db, cfg, user.id)["see_incoming_likes"]:
        raise forbidden("Answering from the Likes list is a Plus feature — they also appear in your Discover pairs.")
    res = svc.respond(db, user.id, interest_id, body.accept)
    return {"state": res.interest.state, "matched": res.match is not None, "match_id": str(res.match.id) if res.match else None}


@router.post("/likes/{interest_id}/cancel")
def cancel(interest_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    it = svc.cancel(db, user.id, interest_id)
    return {"state": it.state}


@router.get("/me/analytics")
def analytics(db: Session = Depends(get_db), user: User = Depends(current_user)):
    cfg = get_config(db)
    if not entitlements(db, cfg, user.id)["profile_analytics"]:
        raise forbidden("Profile analytics are part of Plus")
    impressions = db.scalar(select(func.count()).select_from(PairCandidate).where(PairCandidate.candidate_id == user.id))
    chosen = db.scalar(select(func.count()).select_from(Interest).where(Interest.to_user_id == user.id))
    matches = db.scalar(select(func.count()).select_from(Match).where((Match.user_low_id == user.id) | (Match.user_high_id == user.id)))
    return {
        "times_shown": impressions, "times_chosen": chosen, "matches": matches,
        "note": "Exposure is balanced across eligible people, so these numbers reflect fit and activity, not popularity.",
    }
