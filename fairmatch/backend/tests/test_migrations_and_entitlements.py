import os
import subprocess
import sys
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text

from app.clock import utcnow
from app.models import Subscription
from app.services import entitlements
from tests.conftest import make_user

ADMIN_URL = os.environ["FM_DATABASE_URL"].rsplit("/", 1)[0] + "/postgres"
MIGR_URL = os.environ["FM_DATABASE_URL"].rsplit("/", 1)[0] + "/fairmatch_migration_test"


def test_migrations_upgrade_and_downgrade_cleanly():
    eng = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS fairmatch_migration_test"))
        c.execute(text("CREATE DATABASE fairmatch_migration_test"))
    env = {**os.environ, "FM_DATABASE_URL": MIGR_URL}
    root = os.path.dirname(os.path.dirname(__file__))
    for args in (["upgrade", "head"], ["check"], ["downgrade", "base"], ["upgrade", "head"]):
        r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    eng.dispose()


def _sub(db, user, tier, status, days):
    db.add(Subscription(user_id=user.id, product_id=f"p-{tier}", tier=tier, purchase_token=f"t-{tier}-{status}-{days}",
                        status=status, started_at=utcnow() - timedelta(days=40), expires_at=utcnow() + timedelta(days=days),
                        verified_at=utcnow()))
    db.commit()


@pytest.mark.parametrize("status,days,expected", [
    ("active", 10, "plus"), ("canceled", 10, "plus"), ("grace", 2, "plus"),
    ("expired", 10, "free"), ("revoked", 10, "free"), ("active", -1, "free"), ("on_hold", 10, "free"),
])
def test_entitlement_status_matrix(db, status, days, expected):
    u = make_user(db, "Alice")
    _sub(db, u, "plus", status, days)
    assert entitlements.current_tier(db, u.id) == expected


def test_highest_tier_wins(db):
    u = make_user(db, "Alice")
    _sub(db, u, "plus", "active", 10)
    _sub(db, u, "premium_ai", "active", 10)
    assert entitlements.current_tier(db, u.id) == "premium_ai"
