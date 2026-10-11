import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.db import SessionLocal, get_db
from app.deps import current_user, user_from_token
from app.errors import AppError
from app.models import Match, Message, User
from app.schemas import MessageIn, ReadIn
from app.services import messaging, safety
from app.services.persona import persona_from
from app.services.profile_view import public_profile
from app.services.realtime import hub

router = APIRouter(tags=["matches"])


@router.get("/matches")
def list_matches(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(
        select(Match)
        .where(or_(Match.user_low_id == user.id, Match.user_high_id == user.id), Match.state == "active")
        .order_by(Match.last_message_at.desc().nulls_last(), Match.created_at.desc())
    ).all()
    today = utcnow().date()
    me = persona_from(user, user.profile, today) if user.profile else None
    out = []
    for m in rows:
        other = db.get(User, m.other(user.id))
        if other is None or other.profile is None or other.status not in ("active", "under_review"):
            continue
        last = db.scalars(select(Message).where(Message.match_id == m.id).order_by(Message.id.desc()).limit(1)).first()
        unread = db.scalars(
            select(Message.id).where(Message.match_id == m.id, Message.sender_id != user.id, Message.read_at.is_(None))
        ).all()
        out.append({
            "match_id": str(m.id),
            "created_at": m.created_at.isoformat(),
            "profile": public_profile(me, other, today),
            "last_message": messaging.serialize(last, user.id, messaging.read_receipts_shared(db, user.id, other.id)) if last else None,
            "unread_count": len(unread),
        })
    return {"matches": out}


@router.get("/matches/{match_id}/messages")
def get_messages(match_id: uuid.UUID, before_id: int | None = None, after_id: int | None = None,
                 limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = messaging.get_match_for(db, user.id, match_id)
    rows = messaging.list_messages(db, user.id, match_id, before_id, after_id, limit)
    share = messaging.read_receipts_shared(db, user.id, m.other(user.id))
    return {"messages": [messaging.serialize(r, user.id, share) for r in rows], "match_state": m.state,
            "has_more": len(rows) == limit}


@router.post("/matches/{match_id}/messages", status_code=201)
def send_message(match_id: uuid.UUID, body: MessageIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    msg, _created = messaging.send(db, user.id, match_id, body.body, body.client_message_id)
    m = db.get(Match, match_id)
    return messaging.serialize(msg, user.id, messaging.read_receipts_shared(db, user.id, m.other(user.id)))


@router.post("/matches/{match_id}/read")
def mark_read(match_id: uuid.UUID, body: ReadIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"updated": messaging.mark_read(db, user.id, match_id, body.up_to_id)}


@router.post("/matches/{match_id}/unmatch", status_code=204)
def unmatch(match_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    safety.unmatch(db, user.id, match_id)


def _ws_user(token: str) -> uuid.UUID:
    db = SessionLocal()
    try:
        return user_from_token(db, token).id
    finally:
        db.close()


def _ws_typing(user_id: uuid.UUID, match_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        messaging.typing(db, user_id, match_id)
    finally:
        db.close()


@router.websocket("/ws")
async def websocket(ws: WebSocket):
    """Real-time channel. The client authenticates with its first frame
    ({"type":"auth","token":...}) so tokens never appear in URLs or proxy logs."""
    await ws.accept()
    try:
        first = await ws.receive_json()
        if first.get("type") != "auth":
            raise AppError(401, "unauthenticated", "auth required")
        user_id = await run_in_threadpool(_ws_user, str(first.get("token", "")))
    except Exception:
        await ws.close(code=4401)
        return
    await hub.connect(user_id, ws)
    await ws.send_json({"type": "ready"})
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "typing" and msg.get("match_id"):
                try:
                    await run_in_threadpool(_ws_typing, user_id, uuid.UUID(msg["match_id"]))
                except Exception:
                    pass
            elif msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.disconnect(user_id, ws)
