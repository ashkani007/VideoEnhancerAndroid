import os
import tempfile
import uuid
from datetime import date

os.environ.setdefault("FM_ENV", "test")
os.environ.setdefault("FM_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/fairmatch_test")
os.environ["FM_RUN_BACKGROUND_JOBS"] = "false"
os.environ["FM_REDIS_URL"] = ""
os.environ["FM_LOCAL_MEDIA_DIR"] = tempfile.mkdtemp(prefix="fm-media-")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import db as dbmod  # noqa: E402
from app import models  # noqa: E402
from app.services import app_config  # noqa: E402
from app.services.ratelimit import limiter  # noqa: E402

engine = dbmod.init_engine(os.environ["FM_DATABASE_URL"])
dbmod.Base.metadata.drop_all(engine)
dbmod.Base.metadata.create_all(engine)
TABLES = ", ".join(t.name for t in reversed(dbmod.Base.metadata.sorted_tables))


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    app_config.invalidate_cache()
    limiter.reset()
    yield


@pytest.fixture
def db():
    s = dbmod.SessionLocal()
    try:
        yield s
    finally:
        s.close()


def make_user(
    db,
    name="Alex",
    gender="woman",
    interested_in=("man",),
    dob=date(1995, 5, 1),
    intent="long_term",
    lat=52.37,
    lon=4.89,
    interests=("hiking", "coffee", "film"),
    values=("honesty", "kindness"),
    lifestyle=None,
    communication=None,
    is_demo=False,
    age_min=18,
    age_max=99,
    max_distance_km=100,
    role="user",
    status="active",
    **extra,
):
    u = models.User(
        id=uuid.uuid4(), email=f"{name.lower()}-{uuid.uuid4().hex[:8]}@example.com", password_hash=_PW_HASH,
        date_of_birth=dob, is_demo=is_demo, role=role, status=status,
    )
    u.profile = models.Profile(
        first_name=name, gender=gender, interested_in=list(interested_in), relationship_intent=intent,
        interests=list(interests), values=list(values), lifestyle=lifestyle or {"smoking": "never", "drinking": "socially"},
        communication=communication or {"texting": "often", "planning": "planner"}, dealbreakers=extra.pop("dealbreakers", {}),
        prompts=[], approx_lat=lat, approx_lon=lon, age_min=age_min, age_max=age_max, max_distance_km=max_distance_km,
        completed=True, bio="", **extra,
    )
    u.photos = [models.Photo(storage_key=f"photos/{u.id}/test.jpg", position=0)]
    db.add(u)
    db.commit()
    return u


from app.security import hash_password  # noqa: E402

TEST_PASSWORD = "correct-horse-battery"
_PW_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def auth_headers(client, user) -> dict:
    r = client.post("/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
