"""Push notifications. `log` provider for development; `fcm` uses the FCM HTTP v1 API."""
import json
import logging
import time
import uuid

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DeviceToken

log = logging.getLogger("fairmatch.push")
sent_log: list[dict] = []  # inspected by tests in development mode


class PushProvider:
    def send(self, token: str, title: str, body: str, data: dict) -> None:
        raise NotImplementedError


class LogPushProvider(PushProvider):
    def send(self, token, title, body, data):
        entry = {"token": token[:8] + "…", "title": title, "body": body, "data": data}
        sent_log.append(entry)
        del sent_log[:-200]
        log.info("push(dev) %s", entry)


class FcmPushProvider(PushProvider):  # pragma: no cover - needs Google credentials
    SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

    def __init__(self) -> None:
        s = get_settings()
        if not s.google_service_account_file or not s.fcm_project_id:
            raise RuntimeError("FCM requires FM_GOOGLE_SERVICE_ACCOUNT_FILE and FM_FCM_PROJECT_ID")
        with open(s.google_service_account_file) as f:
            self._sa = json.load(f)
        self._project = s.fcm_project_id
        self._token: tuple[str, float] | None = None

    def _access_token(self) -> str:
        if self._token and self._token[1] > time.time() + 60:
            return self._token[0]
        now = int(time.time())
        assertion = jwt.encode(
            {"iss": self._sa["client_email"], "scope": self.SCOPE, "aud": self._sa["token_uri"], "iat": now, "exp": now + 3600},
            self._sa["private_key"],
            algorithm="RS256",
        )
        r = httpx.post(
            self._sa["token_uri"],
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            timeout=10,
        )
        r.raise_for_status()
        tok = r.json()
        self._token = (tok["access_token"], now + tok.get("expires_in", 3600))
        return self._token[0]

    def send(self, token, title, body, data):
        r = httpx.post(
            f"https://fcm.googleapis.com/v1/projects/{self._project}/messages:send",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            json={"message": {"token": token, "notification": {"title": title, "body": body}, "data": {k: str(v) for k, v in data.items()}}},
            timeout=10,
        )
        if r.status_code >= 400:
            log.warning("FCM send failed %s: %s", r.status_code, r.text[:200])


_provider: PushProvider | None = None


def provider() -> PushProvider:
    global _provider
    if _provider is None:
        _provider = FcmPushProvider() if get_settings().push_provider == "fcm" else LogPushProvider()
    return _provider


def notify_user(db: Session, user_id: uuid.UUID, title: str, body: str, data: dict) -> None:
    """Notification text never contains message bodies or other users' private data."""
    for t in db.scalars(select(DeviceToken.token).where(DeviceToken.user_id == user_id)):
        try:
            provider().send(t, title, body, data)
        except Exception as exc:  # never fail a request because push failed
            log.warning("push failed: %s", exc)
