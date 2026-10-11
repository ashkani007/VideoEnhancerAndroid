"""Seed clearly-labelled FICTIONAL demo profiles.

Demo accounts have users.is_demo = TRUE. Eligibility requires viewer.is_demo == candidate.is_demo,
so demo profiles can never be shown to real accounts (and vice versa).

    python -m app.seed_demo            # creates demo data (idempotent)
    python -m app.seed_demo --reset    # removes all demo data first
"""
import argparse
import random
import uuid
from datetime import date, timedelta

from sqlalchemy import delete, select

from app.clock import utcnow
from app.db import SessionLocal
from app.models import Interest, InterestState, Profile, User
from app.security import hash_password
from app.services.geo import coarsen

DEMO_LOGIN = ("demo@demo.fairmatch.app", "fairmatch-demo-2026")
DEMO_DOMAIN = "demo.fairmatch.app"

PEOPLE = [
    ("Lena", "woman", 27, "long_term", ["climbing", "ceramics", "jazz", "coffee"], ["honesty", "curiosity", "family"], "Architect who sketches strangers' dogs. Looking for someone to get lost in bookshops with."),
    ("Noor", "woman", 29, "long_term_open_short", ["running", "film", "cooking", "travel"], ["kindness", "ambition", "humour"], "Half marathons, full-hearted. Will judge you (lovingly) by your pasta."),
    ("Mira", "woman", 25, "long_term", ["yoga", "poetry", "gardening", "tea"], ["growth", "kindness", "honesty"], "Plant parent of 23. Slow mornings, loud laughs."),
    ("Sofia", "woman", 31, "friendship_first", ["board games", "museums", "baking"], ["loyalty", "curiosity"], "Museum nerd. Best friends first, the rest follows."),
    ("Jade", "woman", 28, "short_term_open_long", ["festivals", "surfing", "photography"], ["adventure", "honesty"], "Chasing waves and good light."),
    ("Aya", "woman", 33, "long_term", ["piano", "hiking", "languages", "coffee"], ["family", "honesty", "faith"], "Teacher by day, terrible pianist by night."),
    ("Elif", "woman", 26, "long_term", ["design", "cycling", "vinyl", "film"], ["creativity", "kindness"], "Collecting records and reasons to cycle somewhere new."),
    ("Chloé", "woman", 30, "figuring_out", ["wine", "theatre", "dancing"], ["humour", "independence"], "Here for good conversation, open to where it leads."),
    ("Luca", "man", 29, "long_term", ["climbing", "coffee", "film", "cooking"], ["honesty", "family", "humour"], "Software engineer who makes a mean risotto. Dog person, cat-tolerant."),
    ("Daniel", "man", 32, "long_term", ["running", "jazz", "books", "travel"], ["kindness", "growth", "honesty"], "Paediatric nurse. Sunday long runs, Monday long naps."),
    ("Omar", "man", 27, "long_term_open_short", ["football", "photography", "coffee"], ["loyalty", "ambition"], "Weekend photographer, weekday optimist."),
    ("Theo", "man", 26, "short_term_open_long", ["skating", "festivals", "music production"], ["creativity", "adventure"], "Making beats and bad puns."),
    ("Kenji", "man", 30, "long_term", ["ceramics", "hiking", "tea", "languages"], ["curiosity", "kindness", "family"], "Potter. My mugs are lopsided but full of love."),
    ("Mateo", "man", 34, "friendship_first", ["board games", "baking", "cycling"], ["humour", "loyalty"], "Will bake you sourdough. Strong opinions about board game rules."),
    ("Ivan", "man", 28, "long_term", ["chess", "museums", "running"], ["honesty", "growth"], "Chess club regular looking for a life partner, not a stalemate."),
    ("Sam", "nonbinary", 27, "long_term", ["poetry", "climbing", "vinyl", "tea"], ["kindness", "creativity", "honesty"], "Bookseller, amateur climber, professional overthinker."),
    ("River", "nonbinary", 30, "long_term_open_short", ["gardening", "film", "cooking"], ["curiosity", "humour"], "Community garden coordinator. Tomatoes are a personality."),
    ("Ari", "nonbinary", 25, "figuring_out", ["dancing", "photography", "travel"], ["adventure", "independence"], "Dancer seeking someone to explore the city with."),
]

PROMPTS = [
    ("A perfect Sunday", "Farmers market, a long walk, and cooking something new together."),
    ("I'm weirdly good at", "Remembering song lyrics from 2009."),
    ("Let's debate", "Is a hot dog a sandwich?"),
    ("Green flag I look for", "Kindness to waiters and patience with plants."),
]

CITY = ("Amsterdam", 52.3676, 4.9041)


def _dob(age: int, rng: random.Random) -> date:
    return date.today() - timedelta(days=365 * age + rng.randint(20, 300))


def reset(db) -> None:
    ids = db.scalars(select(User.id).where(User.is_demo.is_(True))).all()
    if ids:
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()


def seed(db) -> None:
    rng = random.Random(42)
    if db.scalars(select(User).where(User.email == DEMO_LOGIN[0])).first():
        print("Demo data already present.")
        return
    pw = hash_password(DEMO_LOGIN[1])
    created = []
    for name, gender, age, intent, interests, values, bio in PEOPLE:
        lat, lon = coarsen(CITY[1] + rng.uniform(-0.08, 0.08), CITY[2] + rng.uniform(-0.12, 0.12))
        interested = {"woman": ["man", "nonbinary"], "man": ["woman"], "nonbinary": ["everyone"]}[gender]
        if name in ("Sofia", "River"):
            interested = ["everyone"]
        u = User(id=uuid.uuid4(), email=f"{name.lower()}@{DEMO_DOMAIN}", password_hash=pw, date_of_birth=_dob(age, rng),
                 is_demo=True, verification_status=rng.choice(["verified", "verified", "unverified"]))
        q = rng.sample(PROMPTS, 2)
        u.profile = Profile(
            first_name=name, gender=gender, interested_in=interested, relationship_intent=intent, interests=interests,
            values=values, bio=bio, prompts=[{"q": a, "a": b} for a, b in q],
            lifestyle={"smoking": "never", "drinking": rng.choice(["socially", "rarely"]), "exercise": rng.choice(["often", "sometimes"]),
                       "kids_want": rng.choice(["yes", "open", "no"]), "pets": rng.choice(["dog", "cat", "open"])},
            communication={"texting": rng.choice(["often", "flexible"]), "calls": rng.choice(["love", "flexible"]),
                           "planning": rng.choice(["planner", "spontaneous", "flexible"])},
            dealbreakers={}, approx_lat=lat, approx_lon=lon, city_label=CITY[0], age_min=22, age_max=40,
            max_distance_km=50, completed=True, discoverable=True, show_gender=True, show_distance=True,
            read_receipts=True, ai_processing_consent=False, allow_ai_on_my_profile=True,
        )
        db.add(u)
        created.append(u)

    # The demo login: a woman interested in men and nonbinary people.
    lat, lon = coarsen(CITY[1], CITY[2])
    demo = User(id=uuid.uuid4(), email=DEMO_LOGIN[0], password_hash=pw, date_of_birth=_dob(28, rng), is_demo=True,
                verification_status="verified")
    demo.profile = Profile(
        first_name="Robin", gender="woman", interested_in=["man", "nonbinary"], relationship_intent="long_term",
        interests=["climbing", "coffee", "film", "travel"], values=["honesty", "kindness", "humour"],
        bio="Demo account — explore FairMatch with fictional people.", prompts=[{"q": PROMPTS[0][0], "a": PROMPTS[0][1]}],
        lifestyle={"smoking": "never", "drinking": "socially", "exercise": "often"}, communication={"texting": "often", "planning": "flexible"},
        dealbreakers={}, approx_lat=lat, approx_lon=lon, city_label=CITY[0], age_min=22, age_max=40, max_distance_km=50,
        completed=True, discoverable=True, show_gender=True, show_distance=True, read_receipts=True,
        ai_processing_consent=True, allow_ai_on_my_profile=True,
    )
    db.add(demo)
    db.flush()

    # Two fictional people already chose the demo user so the mutual-match moment can be experienced.
    now = utcnow()
    for u in [c for c in created if c.profile.first_name in ("Luca", "Sam")]:
        db.add(Interest(from_user_id=u.id, to_user_id=demo.id, state=InterestState.PENDING.value, created_at=now,
                        delivered_at=now, expires_at=now + timedelta(hours=48), idempotency_key=f"seed-{u.id}"))
    db.commit()
    print(f"Seeded {len(created)} fictional demo profiles. Demo login: {DEMO_LOGIN[0]} / {DEMO_LOGIN[1]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    s = SessionLocal()
    try:
        if args.reset:
            reset(s)
        seed(s)
    finally:
        s.close()
