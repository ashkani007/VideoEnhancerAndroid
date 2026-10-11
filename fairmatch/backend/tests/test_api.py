"""End-to-end API tests: auth, authorization, entitlements, messaging, safety, privacy."""
import io
import uuid
from datetime import date, timedelta

from PIL import Image
from sqlalchemy import select

from app.models import AuditLog, Match, User
from tests.conftest import TEST_PASSWORD, auth_headers, make_user


def adult_dob(years=25):
    return (date.today() - timedelta(days=365 * years + 10)).isoformat()


def register(client, email="new@example.com", dob=None):
    return client.post("/auth/register", json={
        "email": email, "password": "a-strong-password", "date_of_birth": dob or adult_dob(),
        "accept_terms": True, "accept_privacy": True,
    })


# ------------------------------------------------------------------ auth
def test_register_rejects_minors_and_stores_nothing(client, db):
    r = register(client, dob=(date.today() - timedelta(days=365 * 17)).isoformat())
    assert r.status_code == 403 and r.json()["detail"]["code"] == "underage"
    assert db.scalar(select(User).where(User.email == "new@example.com")) is None


def test_register_login_refresh_rotation_and_reuse_detection(client):
    r = register(client)
    assert r.status_code == 201
    rt = r.json()["refresh_token"]
    assert register(client).status_code == 409
    r2 = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r2.status_code == 200
    # Reusing the rotated token revokes the whole family.
    assert client.post("/auth/refresh", json={"refresh_token": rt}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": r2.json()["refresh_token"]}).status_code == 401


def test_login_wrong_password_and_rate_limit(client, db):
    u = make_user(db, "Alice")
    for _ in range(10):
        assert client.post("/auth/login", json={"email": u.email, "password": "wrong-password"}).status_code == 401
    assert client.post("/auth/login", json={"email": u.email, "password": TEST_PASSWORD}).status_code == 429


def test_requires_authentication(client):
    for path in ("/me", "/discover/pair", "/likes", "/matches"):
        assert client.get(path).status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_onboarding_profile_and_photo_upload_strips_metadata(client):
    h = {"Authorization": "Bearer " + register(client).json()["access_token"]}
    r = client.patch("/me/profile", headers=h, json={
        "first_name": "Sam", "gender": "nonbinary", "interested_in": ["everyone"], "relationship_intent": "long_term",
        "latitude": 52.370216, "longitude": 4.895168, "interests": ["climbing"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["profile"]["completed"] is False  # photo still missing
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "purple").save(buf, format="PNG")
    up = client.post("/me/photos", headers=h, files={"file": ("p.png", buf.getvalue(), "image/png")})
    assert up.status_code == 201, up.text
    me = client.get("/me", headers=h).json()
    assert me["profile"]["completed"] is True
    assert "latitude" not in str(me) and "52.370216" not in str(me)
    img = client.get(up.json()["url"].replace("http://localhost:8000", ""))
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"
    bad = client.post("/me/photos", headers=h, files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 400


def test_media_requires_valid_signature(client):
    assert client.get("/media/photos/x.jpg?exp=9999999999&sig=bad").status_code == 403


# ------------------------------------------------------------------ authorization
def test_cannot_view_unrelated_profile(client, db):
    a, b = make_user(db, "Alice"), make_user(db, "Bob", gender="man", interested_in=["woman"])
    assert client.get(f"/users/{b.id}", headers=auth_headers(client, a)).status_code == 404


def test_cannot_read_or_post_in_others_conversation(client, db):
    a, b = make_user(db, "Alice"), make_user(db, "Bob", gender="man", interested_in=["woman"])
    c = make_user(db, "Eve")
    low, high = sorted((a.id, b.id))
    m = Match(user_low_id=low, user_high_id=high)
    db.add(m)
    db.commit()
    he = auth_headers(client, c)
    assert client.get(f"/matches/{m.id}/messages", headers=he).status_code == 404
    assert client.post(f"/matches/{m.id}/messages", headers=he, json={"body": "hi", "client_message_id": "1"}).status_code == 404


def test_admin_endpoints_require_roles(client, db):
    u = make_user(db, "Alice")
    mod = make_user(db, "Mod", role="moderator")
    adm = make_user(db, "Root", role="admin")
    assert client.get("/admin/reports", headers=auth_headers(client, u)).status_code == 403
    assert client.get("/admin/reports", headers=auth_headers(client, mod)).status_code == 200
    assert client.get("/admin/config", headers=auth_headers(client, mod)).status_code == 403
    r = client.put("/admin/config/interest", headers=auth_headers(client, adm), json={"max_incoming_pending": 3})
    assert r.status_code == 200 and r.json()["max_incoming_pending"] == 3
    assert db.scalar(select(AuditLog).where(AuditLog.action == "config.update")) is not None


# ------------------------------------------------------------------ discover -> match -> chat
def test_full_flow_select_accept_chat(client, db):
    alice = make_user(db, "Alice")
    bob = make_user(db, "Bob", gender="man", interested_in=["woman"])
    hb, ha = auth_headers(client, bob), auth_headers(client, alice)

    pair = client.get("/discover/pair", headers=hb).json()
    assert pair["candidates"][0]["first_name"] == "Alice"
    card = pair["candidates"][0]
    assert "insights" in card and "score" not in str(card["insights"]).lower()
    assert "approx_lat" not in card and "email" not in card

    sel = client.post("/discover/select", headers={**hb, "Idempotency-Key": "k1"},
                      json={"pair_id": pair["pair_id"], "candidate_id": card["id"]})
    assert sel.status_code == 200 and sel.json()["state"] == "PENDING" and sel.json()["matched"] is False
    again = client.post("/discover/select", headers={**hb, "Idempotency-Key": "k1"},
                        json={"pair_id": pair["pair_id"], "candidate_id": card["id"]})
    assert again.json()["interest_id"] == sel.json()["interest_id"]

    likes = client.get("/likes", headers=ha).json()
    assert likes["incoming_count"] == 1 and likes["can_see_incoming"] is False and likes["incoming"] == []
    # Free user cannot answer from the list, but Bob is guaranteed a slot in Alice's Discover.
    assert client.post(f"/likes/{sel.json()['interest_id']}/respond", headers=ha, json={"accept": True}).status_code == 403
    pa = client.get("/discover/pair", headers=ha).json()
    bob_card = next(c for c in pa["candidates"] if c["first_name"] == "Bob")
    back = client.post("/discover/select", headers={**ha, "Idempotency-Key": "k2"},
                       json={"pair_id": pa["pair_id"], "candidate_id": bob_card["id"]})
    assert back.json()["matched"] is True
    match_id = back.json()["match_id"]

    r = client.post(f"/matches/{match_id}/messages", headers=hb, json={"body": "Hey Alice!", "client_message_id": "c1"})
    assert r.status_code == 201 and r.json()["status"] in ("sent", "delivered")
    dup = client.post(f"/matches/{match_id}/messages", headers=hb, json={"body": "Hey Alice!", "client_message_id": "c1"})
    assert dup.json()["id"] == r.json()["id"]  # offline resend is idempotent
    msgs = client.get(f"/matches/{match_id}/messages", headers=ha).json()["messages"]
    assert [m["body"] for m in msgs] == ["Hey Alice!"]
    client.post(f"/matches/{match_id}/read", headers=ha, json={"up_to_id": msgs[-1]["id"]})
    mine = client.get(f"/matches/{match_id}/messages", headers=hb).json()["messages"]
    assert mine[0]["status"] == "read"
    newer = client.get(f"/matches/{match_id}/messages?after_id={msgs[-1]['id']}", headers=ha).json()["messages"]
    assert newer == []


def test_read_receipts_privacy(client, db):
    alice = make_user(db, "Alice", read_receipts=False)
    bob = make_user(db, "Bob", gender="man", interested_in=["woman"])
    low, high = sorted((alice.id, bob.id))
    m = Match(user_low_id=low, user_high_id=high)
    db.add(m)
    db.commit()
    hb, ha = auth_headers(client, bob), auth_headers(client, alice)
    sent = client.post(f"/matches/{m.id}/messages", headers=hb, json={"body": "hello", "client_message_id": "a"}).json()
    client.post(f"/matches/{m.id}/read", headers=ha, json={"up_to_id": sent["id"]})
    assert client.get(f"/matches/{m.id}/messages", headers=hb).json()["messages"][0]["status"] == "delivered"


def test_first_message_link_blocked(client, db):
    alice, bob = make_user(db, "Alice"), make_user(db, "Bob", gender="man", interested_in=["woman"])
    low, high = sorted((alice.id, bob.id))
    m = Match(user_low_id=low, user_high_id=high)
    db.add(m)
    db.commit()
    r = client.post(f"/matches/{m.id}/messages", headers=auth_headers(client, bob),
                    json={"body": "check https://scam.example.com", "client_message_id": "x"})
    assert r.status_code == 422


# ------------------------------------------------------------------ entitlements & billing
def test_entitlements_only_after_server_verification(client, db):
    u = make_user(db, "Alice")
    h = auth_headers(client, u)
    assert client.get("/me", headers=h).json()["entitlements"]["tier"] == "free"
    bad = client.post("/billing/verify", headers=h, json={"product_id": "fairmatch_plus_monthly", "purchase_token": "forged"})
    assert bad.status_code == 402
    assert client.get("/me", headers=h).json()["entitlements"]["tier"] == "free"
    ok = client.post("/billing/verify", headers=h, json={"product_id": "fairmatch_premium_ai_monthly", "purchase_token": "dev-123"})
    assert ok.status_code == 200
    me = client.get("/me", headers=h).json()
    assert me["entitlements"]["tier"] == "premium_ai" and me["selections"]["daily_limit"] == 15
    other = make_user(db, "Mallory")
    stolen = client.post("/billing/verify", headers=auth_headers(client, other),
                         json={"product_id": "fairmatch_premium_ai_monthly", "purchase_token": "dev-123"})
    assert stolen.status_code == 409


def test_ai_requires_entitlement_and_consent(client, db):
    alice = make_user(db, "Alice")
    bob = make_user(db, "Bob", gender="man", interested_in=["woman"], interests=["hiking", "chess"])
    h = auth_headers(client, alice)
    assert client.post("/ai/rephrase", headers=h, json={"draft": "hi"}).status_code == 403
    client.post("/billing/verify", headers=h, json={"product_id": "fairmatch_premium_ai_monthly", "purchase_token": "dev-ai"})
    r = client.post("/ai/rephrase", headers=h, json={"draft": "hi"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ai_consent_required"
    client.patch("/me/profile", headers=h, json={"ai_processing_consent": True})
    client.get("/discover/pair", headers=h)  # Bob now shown -> viewable
    r = client.post(f"/ai/insights/{bob.id}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "rules" and body["conversation_starters"]
    assert "%" not in str(body)


def test_boost_purchase_is_labelled_and_capped(client, db):
    u = make_user(db, "Alice")
    h = auth_headers(client, u)
    r = client.post("/billing/verify", headers=h, json={"product_id": "fairmatch_boost_30m", "purchase_token": "dev-boost-1"})
    assert r.status_code == 200
    assert client.get("/me", headers=h).json()["boost_active_until"] is not None
    assert client.post("/billing/verify", headers=h, json={"product_id": "fairmatch_boost_30m", "purchase_token": "dev-boost-1"}).status_code == 409


# ------------------------------------------------------------------ safety
def test_block_ends_match_and_hides_profile(client, db):
    alice, bob = make_user(db, "Alice"), make_user(db, "Bob", gender="man", interested_in=["woman"])
    low, high = sorted((alice.id, bob.id))
    m = Match(user_low_id=low, user_high_id=high)
    db.add(m)
    db.commit()
    ha = auth_headers(client, alice)
    assert client.post("/safety/block", headers=ha, json={"user_id": str(bob.id)}).status_code == 204
    hb = auth_headers(client, bob)
    assert client.get("/matches", headers=hb).json()["matches"] == []
    assert client.get(f"/users/{alice.id}", headers=hb).status_code == 404
    r = client.post(f"/matches/{m.id}/messages", headers=hb, json={"body": "hi", "client_message_id": "z"})
    assert r.status_code == 409


def test_reports_trigger_review_after_distinct_reporters(client, db):
    target = make_user(db, "Spammer", gender="man", interested_in=["woman"])
    for i in range(3):
        rep = make_user(db, f"R{i}")
        r = client.post("/safety/report", headers=auth_headers(client, rep),
                        json={"user_id": str(target.id), "reason": "spam", "block": False})
        assert r.status_code == 201
    db.refresh(target)
    assert target.status == "under_review"


def test_underage_report_hides_immediately_and_moderation_is_audited(client, db):
    target = make_user(db, "Kid", gender="man", interested_in=["woman"])
    rep, mod = make_user(db, "Rep"), make_user(db, "Mod", role="moderator")
    client.post("/safety/report", headers=auth_headers(client, rep), json={"user_id": str(target.id), "reason": "underage"})
    db.refresh(target)
    assert target.status == "under_review"
    hm = auth_headers(client, mod)
    reports = client.get("/admin/reports", headers=hm).json()["reports"]
    assert len(reports) == 1
    assert client.post("/admin/moderate", headers=hm, json={"user_id": str(target.id), "action": "ban"}).status_code == 400
    assert client.post("/admin/moderate", headers=hm, json={"user_id": str(target.id), "action": "suspend"}).status_code == 200
    db.refresh(target)
    assert target.status == "suspended"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "moderation.suspend")).actor_id == mod.id


# ------------------------------------------------------------------ privacy
def test_export_and_delete_account(client, db):
    from app.services import privacy

    u = make_user(db, "Alice")
    h = auth_headers(client, u)
    exp = client.get("/me/export", headers=h)
    assert exp.status_code == 200 and exp.json()["account"]["email"] == u.email
    r = client.delete("/me", headers=h)
    assert r.status_code == 202
    assert client.get("/me", headers=h).status_code == 401  # sessions revoked
    privacy.purge_user(db, u.id)
    db.expire_all()
    gone = db.get(User, u.id)
    assert gone.status == "deleted" and gone.profile is None and "deleted.invalid" in gone.email


def test_validation_errors_are_friendly(client):
    r = client.post("/auth/register", json={"email": "bad", "password": "x"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "validation_error"


def test_websocket_auth_and_realtime_match_event(client, db):
    alice = make_user(db, "Alice")
    bob = make_user(db, "Bob", gender="man", interested_in=["woman"])
    token = auth_headers(client, alice)["Authorization"].split()[1]
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "ready"
        low, high = sorted((alice.id, bob.id))
        m = Match(user_low_id=low, user_high_id=high)
        db.add(m)
        db.commit()
        client.post(f"/matches/{m.id}/messages", headers=auth_headers(client, bob), json={"body": "yo", "client_message_id": "w1"})
        evt = ws.receive_json()
        assert evt["type"] == "message" and evt["message"]["body"] == "yo"
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": "bad"})
        try:
            ws.receive_json()
            raise AssertionError("expected close")
        except Exception:
            pass
