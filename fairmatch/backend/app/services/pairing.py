"""Two-choice pair generation: eligibility -> compatibility -> fair exposure -> diversity."""
import math
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.clock import utcnow
from app.errors import conflict, not_found
from app.models import (
    ACTIVE_INTEREST_STATES,
    Block,
    Interest,
    InterestState as S,
    Match,
    PairCandidate,
    PairPresentation,
    Profile,
    User,
)
from app.services import compatibility, fairness
from app.services.app_config import get_config
from app.services.eligibility import distance_km, is_mutually_eligible
from app.services.entitlements import boosted_user_ids
from app.services.interests import _quota_row, lock_users, reject_incoming_from
from app.services.persona import Persona, persona_from


@dataclass
class ScoredCandidate:
    user: User
    persona: Persona
    compat: float | None
    rank: float
    boosted_promotion: bool
    incoming: bool


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year + years, day=28)


def candidate_pool(db: Session, viewer: User, now: datetime, cfg: dict) -> list[User]:
    """SQL prefilter (cheap, index-friendly). Exact reciprocal checks happen in Python."""
    vp: Profile = viewer.profile
    today = now.date()
    mcfg = cfg["matching"]
    oldest_dob = _add_years(today, -(vp.age_max + 1))
    youngest_dob = _add_years(today, -vp.age_min)

    blocked = select(Block.blocked_id).where(Block.blocker_id == viewer.id).union(
        select(Block.blocker_id).where(Block.blocked_id == viewer.id)
    )
    matched = select(Match.user_high_id).where(Match.user_low_id == viewer.id).union(
        select(Match.user_low_id).where(Match.user_high_id == viewer.id)
    )
    # Anyone the viewer already chose (active or resolved) is not shown again.
    already_chosen = select(Interest.to_user_id).where(Interest.from_user_id == viewer.id)
    cooldown = now - timedelta(days=mcfg["repeat_cooldown_days"])
    recently_passed = select(PairCandidate.candidate_id).where(
        PairCandidate.viewer_id == viewer.id, PairCandidate.state == "PASSED", PairCandidate.created_at >= cooldown
    )
    # People who declined the viewer are never resurfaced to the viewer.
    declined_viewer = select(Interest.from_user_id).where(
        Interest.to_user_id == viewer.id, Interest.state == S.REJECTED.value
    )

    q = (
        select(User)
        .join(Profile, Profile.user_id == User.id)
        .options(selectinload(User.profile), selectinload(User.photos))
        .where(
            User.id != viewer.id,
            User.status == "active",
            User.is_demo == viewer.is_demo,
            Profile.completed.is_(True),
            Profile.discoverable.is_(True),
            User.date_of_birth > oldest_dob,
            User.date_of_birth <= youngest_dob,
            or_(Profile.interested_in.any(vp.gender), Profile.interested_in.any("everyone")),
            User.id.not_in(blocked),
            User.id.not_in(matched),
            User.id.not_in(already_chosen),
            User.id.not_in(recently_passed),
            User.id.not_in(declined_viewer),
        )
        .order_by(User.last_active_at.desc())
        .limit(mcfg["candidate_pool_limit"])
    )
    if "everyone" not in (vp.interested_in or []):
        q = q.where(Profile.gender.in_(vp.interested_in or ["__none__"]))
    return list(db.scalars(q).unique())


def _similarity(a: Persona, b: Persona) -> float:
    ia, ib = set(a.interests), set(b.interests)
    j = len(ia & ib) / len(ia | ib) if ia and ib else 0.0
    same_intent = 1.0 if a.relationship_intent and a.relationship_intent == b.relationship_intent else 0.0
    return 0.6 * j + 0.4 * same_intent


def rank_candidates(
    viewer: Persona,
    candidates: list[tuple[User, Persona]],
    impressions: dict[uuid.UUID, int],
    incoming: set[uuid.UUID],
    inbox_full: set[uuid.UUID],
    boosted: set[uuid.UUID],
    boost_allowed: bool,
    cfg: dict,
    now: datetime,
) -> list[ScoredCandidate]:
    mcfg = cfg["matching"]
    med = fairness.pool_median([impressions.get(p.id, 0) for _, p in candidates])
    out = []
    for user, p in candidates:
        res = compatibility.score(viewer, p, mcfg["weights"], distance_km(viewer, p))
        compat = res.score if res.score is not None else 0.5
        rank = fairness.blended_score(compat, impressions.get(p.id, 0), med, mcfg["fairness_lambda"])
        is_incoming = p.id in incoming
        if is_incoming:
            rank += mcfg["incoming_interest_bonus"]
        promo = boost_allowed and p.id in boosted
        if promo:
            rank += mcfg["boost_bonus"]
        if p.id in inbox_full and not is_incoming:
            rank *= mcfg["full_inbox_penalty"]
        if p.last_active_at is not None and now - p.last_active_at > timedelta(days=7):
            rank *= 0.85
        out.append(ScoredCandidate(user, p, res.score, rank, promo, is_incoming))
    out.sort(key=lambda c: c.rank, reverse=True)
    return out


def choose_pair(ranked: list[ScoredCandidate], cfg: dict, rng: random.Random) -> list[ScoredCandidate]:
    if not ranked:
        return []
    mcfg = cfg["matching"]
    incoming = [c for c in ranked if c.incoming]
    if incoming:
        # Someone who already chose the viewer is always given a slot so the viewer can
        # answer for free, regardless of subscription tier.
        first = incoming[0]
    else:
        top = ranked[: mcfg["top_k_sampling"]]
        weights = [math.exp(4 * c.rank) for c in top]
        first = rng.choices(top, weights=weights, k=1)[0]
    rest = [c for c in ranked if c is not first]
    if not rest:
        return [first]
    # At most one boost-promoted card per pair.
    if first.boosted_promotion:
        rest = [c for c in rest if not c.boosted_promotion] or rest
    second = max(rest, key=lambda c: c.rank - mcfg["diversity_penalty"] * _similarity(first.persona, c.persona))
    return [first, second]


def _impressions(db: Session, ids: list[uuid.UUID], since: datetime) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(PairCandidate.candidate_id, func.count())
        .where(PairCandidate.candidate_id.in_(ids), PairCandidate.created_at >= since)
        .group_by(PairCandidate.candidate_id)
    ).all()
    return {cid: n for cid, n in rows}


def current_open_pair(db: Session, viewer_id: uuid.UUID) -> PairPresentation | None:
    return db.scalars(
        select(PairPresentation)
        .where(PairPresentation.viewer_id == viewer_id, PairPresentation.state == "open")
        .order_by(PairPresentation.created_at.desc())
    ).first()


def _still_valid(db: Session, viewer: User, pair: PairPresentation, now: datetime) -> bool:
    today = now.date()
    vp = persona_from(viewer, viewer.profile, today)
    for c in pair.candidates:
        u = db.get(User, c.candidate_id)
        if u is None or u.profile is None:
            return False
        blocked = db.scalar(
            select(func.count()).select_from(Block).where(
                or_(
                    and_(Block.blocker_id == viewer.id, Block.blocked_id == u.id),
                    and_(Block.blocker_id == u.id, Block.blocked_id == viewer.id),
                )
            )
        )
        if not is_mutually_eligible(vp, persona_from(u, u.profile, today), blocked=bool(blocked)):
            return False
    return True


def get_or_create_pair(db: Session, viewer_id: uuid.UUID, rng: random.Random | None = None) -> PairPresentation | None:
    rng = rng or random.Random()
    now = utcnow()
    cfg = get_config(db)
    try:
        lock_users(db, viewer_id)
        viewer = db.get(User, viewer_id)
        if viewer is None or viewer.profile is None or not viewer.profile.completed:
            raise conflict("profile_incomplete", "Complete your profile to start discovering")

        existing = current_open_pair(db, viewer_id)
        if existing is not None:
            if _still_valid(db, viewer, existing, now):
                db.commit()
                return existing
            existing.state, existing.resolved_at = "superseded", now

        today = now.date()
        vp = persona_from(viewer, viewer.profile, today)
        pool = candidate_pool(db, viewer, now, cfg)
        eligible = [(u, persona_from(u, u.profile, today)) for u in pool]
        eligible = [(u, p) for u, p in eligible if is_mutually_eligible(vp, p)]
        if not eligible:
            db.commit()
            return None

        ids = [p.id for _, p in eligible]
        since = now - timedelta(days=cfg["matching"]["exposure_window_days"])
        impressions = _impressions(db, ids, since)
        incoming = set(
            db.scalars(
                select(Interest.from_user_id).where(
                    Interest.to_user_id == viewer_id,
                    Interest.from_user_id.in_(ids),
                    Interest.state.in_((S.PENDING.value, S.WAITLISTED.value)),
                )
            )
        )
        cap = cfg["interest"]["max_incoming_pending"]
        inbox_full = set(
            db.scalars(
                select(Interest.to_user_id)
                .where(Interest.to_user_id.in_(ids), Interest.state == S.PENDING.value)
                .group_by(Interest.to_user_id)
                .having(func.count() >= cap)
            )
        )
        quota = _quota_row(db, viewer_id, now)
        boost_ok = fairness.boost_slot_allowed(quota.boosted_slots, quota.total_slots, cfg["matching"]["boost_inventory_cap"])
        boosted = boosted_user_ids(db, ids, now)

        ranked = rank_candidates(vp, eligible, impressions, incoming, inbox_full, boosted, boost_ok, cfg, now)
        chosen = choose_pair(ranked, cfg, rng)

        pair = PairPresentation(id=uuid.uuid4(), viewer_id=viewer_id, state="open", created_at=now)
        db.add(pair)
        for slot, c in enumerate(chosen):
            pair.candidates.append(
                PairCandidate(
                    viewer_id=viewer_id, candidate_id=c.user.id, slot=slot, state=S.PROPOSED.value,
                    boosted=c.boosted_promotion, created_at=now,
                )
            )
        quota.total_slots += len(chosen)
        quota.boosted_slots += sum(1 for c in chosen if c.boosted_promotion)
        db.commit()
        return pair
    except Exception:
        db.rollback()
        raise


def pass_pair(db: Session, viewer_id: uuid.UUID, pair_id: uuid.UUID) -> None:
    """'Neither for now' — never forces a choice and costs no selections."""
    now = utcnow()
    cfg = get_config(db)
    try:
        lock_users(db, viewer_id)
        pair = db.scalars(select(PairPresentation).where(PairPresentation.id == pair_id).with_for_update()).first()
        if pair is None or pair.viewer_id != viewer_id:
            raise not_found("Pair")
        if pair.state != "open":
            raise conflict("pair_closed", "This pair has already been resolved")
        pair.state, pair.resolved_at = "passed", now
        for c in pair.candidates:
            c.state = "PASSED"
        reject_incoming_from(db, viewer_id, [c.candidate_id for c in pair.candidates], "viewer_passed", now, cfg)
        db.commit()
    except Exception:
        db.rollback()
        raise


def exposure_snapshot(db: Session, now: datetime | None = None) -> dict:
    """Admin monitoring: exposure inequality among active, discoverable, non-demo users."""
    now = now or utcnow()
    cfg = get_config(db)
    since = now - timedelta(days=cfg["matching"]["exposure_window_days"])
    ids = list(
        db.scalars(
            select(User.id).join(Profile).where(
                User.status == "active", User.is_demo.is_(False), Profile.completed.is_(True), Profile.discoverable.is_(True)
            )
        )
    )
    imp = _impressions(db, ids, since)
    report = fairness.exposure_report([imp.get(i, 0) for i in ids])
    report["window_days"] = cfg["matching"]["exposure_window_days"]
    return report
