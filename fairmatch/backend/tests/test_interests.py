"""Interest queue, state machine, capacity, quotas, idempotency and mutual matching (PostgreSQL)."""
import random
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.errors import AppError
from app.models import Interest, InterestEvent, InterestState as S, Match, PairCandidate, PairPresentation
from app.services import interests as svc
from app.services import pairing
from app.services.interests import TRANSITIONS, can_transition
from tests.conftest import make_user


def force_pair(db, viewer, *cands):
    pair = PairPresentation(id=uuid.uuid4(), viewer_id=viewer.id, state="open")
    for i, c in enumerate(cands):
        pair.candidates.append(PairCandidate(viewer_id=viewer.id, candidate_id=c.id, slot=i))
    db.add(pair)
    db.commit()
    return pair


def choose(db, viewer, target, key=None):
    pair = force_pair(db, viewer, target)
    return svc.select_candidate(db, viewer.id, pair.id, target.id, key or uuid.uuid4().hex)


def men(db, n, **kw):
    return [make_user(db, name=f"M{i}", gender="man", interested_in=["woman"], **kw) for i in range(n)]


def test_state_machine_rejects_invalid_transitions():
    assert can_transition(None, S.SELECTED)
    assert can_transition(S.SELECTED, S.PENDING)
    assert can_transition(S.WAITLISTED, S.PENDING)
    assert not can_transition(S.MATCHED, S.PENDING)
    assert not can_transition(S.EXPIRED, S.MATCHED)
    assert not can_transition(S.PENDING, S.WAITLISTED)
    assert not can_transition(None, S.PENDING)
    for terminal in (S.MATCHED, S.REJECTED, S.EXPIRED, S.CANCELED):
        assert TRANSITIONS[terminal] == set()


def test_pending_capacity_and_waitlist(db):
    alice = make_user(db, "Alice")
    suitors = men(db, 4)
    states = [choose(db, m, alice).interest.state for m in suitors]
    assert states == ["PENDING", "PENDING", "WAITLISTED", "WAITLISTED"]
    # Recipient only sees delivered requests, never waitlisted ones.
    assert len(svc.incoming_pending(db, alice.id)) == 2
    # History recorded SELECTED -> PENDING/WAITLISTED.
    assert db.scalar(select(func.count()).select_from(InterestEvent)) == 8


def test_decline_promotes_oldest_waitlisted(db):
    alice = make_user(db, "Alice")
    m = men(db, 3)
    i0 = choose(db, m[0], alice).interest
    choose(db, m[1], alice)
    i2 = choose(db, m[2], alice).interest
    assert i2.state == "WAITLISTED"
    svc.respond(db, alice.id, i0.id, accept=False)
    db.refresh(i2)
    assert i2.state == "PENDING" and i2.expires_at is not None


def test_accept_creates_single_match(db):
    alice = make_user(db, "Alice")
    bob = men(db, 1)[0]
    it = choose(db, bob, alice).interest
    res = svc.respond(db, alice.id, it.id, accept=True)
    assert res.match is not None and res.interest.state == "MATCHED"
    with pytest.raises(AppError):
        svc.respond(db, alice.id, it.id, accept=True)
    assert db.scalar(select(func.count()).select_from(Match)) == 1


def test_mutual_selection_matches_immediately_and_is_free(db):
    alice = make_user(db, "Alice")
    bob = men(db, 1)[0]
    first = choose(db, bob, alice)
    assert first.interest.state == "PENDING" and first.match is None
    before, _ = svc.remaining_selections(db, alice.id)
    second = choose(db, alice, bob)
    assert second.match is not None
    db.refresh(first.interest)
    assert first.interest.state == "MATCHED"
    after, _ = svc.remaining_selections(db, alice.id)
    assert after == before  # choosing back someone who chose you costs nothing


def test_expiry_after_48h_and_promotion(db, monkeypatch):
    alice = make_user(db, "Alice")
    m = men(db, 3)
    i0 = choose(db, m[0], alice).interest
    i1 = choose(db, m[1], alice).interest
    i2 = choose(db, m[2], alice).interest
    future = i0.expires_at + timedelta(minutes=1)
    assert svc.expire_due(db, now=future) >= 2
    for it in (i0, i1, i2):
        db.refresh(it)
    assert i0.state == "EXPIRED" and i1.state == "EXPIRED"
    assert i2.state == "PENDING"  # delivered once capacity freed


def test_daily_quota_free_vs_plus(db):
    from app.models import Subscription
    from app.clock import utcnow

    bob = make_user(db, "Bob", gender="man", interested_in=["woman"])
    women = [make_user(db, f"W{i}") for i in range(7)]
    for w in women[:5]:
        choose(db, bob, w)
    with pytest.raises(AppError) as e:
        choose(db, bob, women[5])
    assert e.value.code == "daily_limit_reached"
    db.add(Subscription(user_id=bob.id, product_id="fairmatch_plus_monthly", tier="plus", purchase_token="dev-x",
                        status="active", started_at=utcnow(), expires_at=utcnow() + timedelta(days=30), verified_at=utcnow()))
    db.commit()
    assert choose(db, bob, women[5]).interest.state == "PENDING"
    remaining, limit = svc.remaining_selections(db, bob.id)
    assert limit == 15 and remaining == 9


def test_idempotent_replay_and_duplicate_prevention(db):
    alice = make_user(db, "Alice")
    bob = men(db, 1)[0]
    pair = force_pair(db, bob, alice)
    r1 = svc.select_candidate(db, bob.id, pair.id, alice.id, "key-1")
    r2 = svc.select_candidate(db, bob.id, pair.id, alice.id, "key-1")
    assert r2.idempotent_replay and r2.interest.id == r1.interest.id
    with pytest.raises(AppError) as e:
        choose(db, bob, alice)  # new key, same person while active
    assert e.value.code == "already_interested"
    assert db.scalar(select(func.count()).select_from(Interest)) == 1


def test_cancel_frees_capacity(db):
    alice = make_user(db, "Alice")
    m = men(db, 3)
    i0 = choose(db, m[0], alice).interest
    choose(db, m[1], alice)
    i2 = choose(db, m[2], alice).interest
    svc.cancel(db, m[0].id, i0.id)
    db.refresh(i2)
    assert i2.state == "PENDING"
    with pytest.raises(AppError):
        svc.cancel(db, m[0].id, i0.id)  # already terminal


def test_cannot_select_outside_pair_or_blocked(db):
    from app.services import safety

    alice = make_user(db, "Alice")
    bob, carl = men(db, 2)
    pair = force_pair(db, bob, alice)
    with pytest.raises(AppError):
        svc.select_candidate(db, bob.id, pair.id, carl.id, "k")
    safety.block(db, alice.id, bob.id)
    with pytest.raises(AppError) as e:
        svc.select_candidate(db, bob.id, pair.id, alice.id, "k2")
    assert e.value.code == "unavailable"


def test_pair_generation_respects_eligibility_and_demo_separation(db):
    alice = make_user(db, "Alice")
    good = men(db, 3)
    make_user(db, "Demo", gender="man", interested_in=["woman"], is_demo=True)
    make_user(db, "Gay", gender="man", interested_in=["man"])
    make_user(db, "Far", gender="man", interested_in=["woman"], lat=40.4, lon=-3.7)
    make_user(db, "Young", gender="man", interested_in=["woman"], dob=date.today() - timedelta(days=365 * 17))
    pair = pairing.get_or_create_pair(db, alice.id, random.Random(1))
    ids = {c.candidate_id for c in pair.candidates}
    assert len(ids) == 2 and ids <= {m.id for m in good}
    # Same open pair is returned until resolved (no re-rolling for better options).
    assert pairing.get_or_create_pair(db, alice.id).id == pair.id


def test_pass_both_never_reshows_and_handles_small_pool(db):
    alice = make_user(db, "Alice")
    m = men(db, 3)
    p1 = pairing.get_or_create_pair(db, alice.id, random.Random(2))
    shown = {c.candidate_id for c in p1.candidates}
    pairing.pass_pair(db, alice.id, p1.id)
    p2 = pairing.get_or_create_pair(db, alice.id, random.Random(3))
    assert len(p2.candidates) == 1  # only one unseen candidate left: honest single card
    assert p2.candidates[0].candidate_id not in shown
    pairing.pass_pair(db, alice.id, p2.id)
    assert pairing.get_or_create_pair(db, alice.id) is None  # no fabricated candidates


def test_incoming_interest_gets_a_slot_and_pass_rejects_it(db):
    alice = make_user(db, "Alice")
    m = men(db, 6)
    it = choose(db, m[5], alice).interest
    pair = pairing.get_or_create_pair(db, alice.id, random.Random(4))
    assert m[5].id in {c.candidate_id for c in pair.candidates}
    pairing.pass_pair(db, alice.id, pair.id)
    db.refresh(it)
    assert it.state == "REJECTED"


def test_blocked_users_never_paired(db):
    from app.services import safety

    alice = make_user(db, "Alice")
    m = men(db, 3)
    safety.block(db, m[0].id, alice.id)
    for seed in range(5):
        p = pairing.get_or_create_pair(db, alice.id, random.Random(seed))
        assert m[0].id not in {c.candidate_id for c in p.candidates}
