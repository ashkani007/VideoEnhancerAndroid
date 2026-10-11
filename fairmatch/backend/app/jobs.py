"""Periodic maintenance: interest expiry/waitlist promotion and GDPR purge."""
import asyncio
import logging

from fastapi.concurrency import run_in_threadpool

from app.db import SessionLocal
from app.services import interests, privacy

log = logging.getLogger("fairmatch.jobs")


def run_once() -> dict:
    db = SessionLocal()
    try:
        return {"expired": interests.expire_due(db), "purged": privacy.purge_due(db)}
    finally:
        db.close()


async def loop(interval_s: int = 60) -> None:
    while True:
        try:
            result = await run_in_threadpool(run_once)
            if any(result.values()):
                log.info("maintenance %s", result)
        except Exception as exc:  # keep the loop alive
            log.exception("maintenance failed: %s", exc)
        await asyncio.sleep(interval_s)
