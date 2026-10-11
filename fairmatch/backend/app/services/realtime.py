"""WebSocket fan-out hub.

Single instance: delivers directly to sockets held by this process.
Multi instance: when FM_REDIS_URL is set, events are published on Redis pub/sub and every
instance forwards them to its local sockets.
"""
import asyncio
import json
import logging
import uuid
from collections import defaultdict

from fastapi import WebSocket

log = logging.getLogger("fairmatch.realtime")
CHANNEL = "fm:events"


class Hub:
    def __init__(self) -> None:
        self._sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._redis_sync = None
        self._redis_url: str | None = None
        self._listener: asyncio.Task | None = None

    async def start(self, redis_url: str | None) -> None:
        self._loop = asyncio.get_running_loop()
        self._redis_url = redis_url
        if redis_url:
            try:
                import redis
                import redis.asyncio as aioredis

                self._redis_sync = redis.Redis.from_url(redis_url)
                self._redis_sync.ping()
                self._listener = asyncio.create_task(self._listen(aioredis.Redis.from_url(redis_url)))
            except Exception as exc:  # pragma: no cover - depends on infra
                log.warning("Redis unavailable for realtime fan-out, using local delivery: %s", exc)
                self._redis_sync = None

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()

    async def _listen(self, r) -> None:  # pragma: no cover - requires redis
        pubsub = r.pubsub()
        await pubsub.subscribe(CHANNEL)
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            data = json.loads(msg["data"])
            await self._deliver_local(data["user_id"], data["event"])

    def online(self, user_id: uuid.UUID) -> bool:
        return bool(self._sockets.get(str(user_id)))

    async def connect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self._sockets[str(user_id)].add(ws)

    def disconnect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self._sockets[str(user_id)].discard(ws)

    async def _deliver_local(self, user_id: str, event: dict) -> None:
        for ws in list(self._sockets.get(user_id, ())):
            try:
                await ws.send_json(event)
            except Exception:
                self._sockets[user_id].discard(ws)

    def publish(self, user_id: uuid.UUID, event: dict) -> None:
        """Thread-safe; callable from sync request handlers."""
        uid = str(user_id)
        if self._redis_sync is not None:
            try:
                self._redis_sync.publish(CHANNEL, json.dumps({"user_id": uid, "event": event}, default=str))
                return
            except Exception as exc:  # pragma: no cover
                log.warning("Redis publish failed, delivering locally: %s", exc)
        if self._loop is None or self._loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            self._loop.create_task(self._deliver_local(uid, event))
        else:
            asyncio.run_coroutine_threadsafe(self._deliver_local(uid, event), self._loop)


hub = Hub()
