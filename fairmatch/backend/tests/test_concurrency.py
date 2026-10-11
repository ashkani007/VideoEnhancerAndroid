"""Race-condition tests: real threads, separate sessions, real PostgreSQL row locks."""
import threading
import uuid

from sqlalchemy import func, select

from app import db as dbmod
from app.errors import AppError
from app.models import Interest, Match
from app.services import interests as svc
from tests.conftest import make_user
from tests.test_interests import force_pair


def run_parallel(fns):
    barrier = threading.Barrier(len(fns))
    results, errors = [None] * len(fns), [None] * len(fns)

    def wrap(i, fn):
        s = dbmod.SessionLocal()
        try:
            barrier.wait()
            results[i] = fn(s)
        except Exception as exc:  # collected for assertions
            errors[i] = exc
        finally:
            s.close()

    threads = [threading.Thread(target=wrap, args=(i, f)) for i, f in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return results, errors


def test_simultaneous_requests_never_exceed_pending_capacity(db):
    alice = make_user(db, "Alice")
    suitors = [make_user(db, f"M{i}", gender="man", interested_in=["woman"]) for i in range(12)]
    pairs = [force_pair(db, m, alice) for m in suitors]
    fns = [lambda s, m=m, p=p: svc.select_candidate(s, m.id, p.id, alice.id, uuid.uuid4().hex).interest.state
           for m, p in zip(suitors, pairs)]
    results, errors = run_parallel(fns)
    assert not any(errors), errors
    assert results.count("PENDING") == 2
    assert results.count("WAITLISTED") == 10
    assert db.scalar(select(func.count()).select_from(Interest).where(Interest.to_user_id == alice.id, Interest.state == "PENDING")) == 2


def test_simultaneous_mutual_selection_creates_exactly_one_match(db):
    for _ in range(5):
        a = make_user(db, "A")
        b = make_user(db, "B", gender="man", interested_in=["woman"])
        pa, pb = force_pair(db, a, b), force_pair(db, b, a)
        results, errors = run_parallel([
            lambda s: svc.select_candidate(s, a.id, pa.id, b.id, uuid.uuid4().hex),
            lambda s: svc.select_candidate(s, b.id, pb.id, a.id, uuid.uuid4().hex),
        ])
        assert not any(errors), errors
        low, high = sorted((a.id, b.id))
        assert db.scalar(select(func.count()).select_from(Match).where(Match.user_low_id == low, Match.user_high_id == high)) == 1
        states = sorted(db.scalars(select(Interest.state).where(Interest.from_user_id.in_([a.id, b.id]))).all())
        assert states == ["MATCHED", "MATCHED"]


def test_concurrent_same_idempotency_key_creates_one_interest(db):
    alice = make_user(db, "Alice")
    bob = make_user(db, "Bob", gender="man", interested_in=["woman"])
    pair = force_pair(db, bob, alice)
    results, errors = run_parallel([lambda s: svc.select_candidate(s, bob.id, pair.id, alice.id, "same-key").interest.id] * 6)
    assert not any(errors), errors
    assert len(set(results)) == 1  # every retry observes the same interest
    assert db.scalar(select(func.count()).select_from(Interest)) == 1


def test_concurrent_selections_respect_daily_quota(db):
    bob = make_user(db, "Bob", gender="man", interested_in=["woman"])
    women = [make_user(db, f"W{i}") for i in range(10)]
    pairs = [force_pair(db, bob, w) for w in women]
    fns = [lambda s, w=w, p=p: svc.select_candidate(s, bob.id, p.id, w.id, uuid.uuid4().hex) for w, p in zip(women, pairs)]
    results, errors = run_parallel(fns)
    assert sum(r is not None for r in results) == 5
    assert all(isinstance(e, AppError) and e.code == "daily_limit_reached" for e in errors if e is not None)


def test_concurrent_accept_and_cancel_resolve_consistently(db):
    for _ in range(5):
        alice = make_user(db, "Alice")
        bob = make_user(db, "Bob", gender="man", interested_in=["woman"])
        pair = force_pair(db, bob, alice)
        it = svc.select_candidate(db, bob.id, pair.id, alice.id, uuid.uuid4().hex).interest
        results, errors = run_parallel([
            lambda s: svc.respond(s, alice.id, it.id, True),
            lambda s: svc.cancel(s, bob.id, it.id),
        ])
        assert sum(e is None for e in errors) == 1  # exactly one wins
        db.expire_all()
        final = db.get(Interest, it.id).state
        matches = db.scalar(select(func.count()).select_from(Match).where(Match.user_low_id.in_([alice.id, bob.id])))
        assert (final == "MATCHED" and matches == 1) or (final == "CANCELED" and matches == 0)
