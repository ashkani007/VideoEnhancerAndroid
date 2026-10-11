"""Purchase verification. Entitlements are granted ONLY after the server verifies a purchase
token with Google Play (or, in development, with the clearly-labelled DevVerifier)."""
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.config import get_settings
from app.errors import AppError, bad_request, conflict
from app.models import Boost, Subscription
from app.services.app_config import get_config
from app.services.audit import audit


@dataclass
class VerifiedPurchase:
    product_id: str
    kind: str  # subscription | consumable
    status: str  # active | grace | on_hold | canceled | expired | revoked | purchased
    expires_at: datetime | None
    auto_renewing: bool
    raw: dict
    needs_ack: bool = False


class Verifier:
    def verify(self, product_id: str, token: str, kind: str) -> VerifiedPurchase:
        raise NotImplementedError

    def acknowledge(self, product_id: str, token: str, kind: str) -> None:
        pass


class DevVerifier(Verifier):
    """DEVELOPMENT ONLY. Accepts tokens shaped `dev-<anything>`; refuses to run in production."""

    def __init__(self) -> None:
        if get_settings().is_production:
            raise RuntimeError("DevVerifier cannot be used in production")

    def verify(self, product_id, token, kind):
        if not token.startswith("dev-"):
            raise AppError(402, "purchase_invalid", "Purchase could not be verified")
        now = utcnow()
        if kind == "subscription":
            return VerifiedPurchase(product_id, kind, "active", now + timedelta(days=30), True, {"dev": True})
        return VerifiedPurchase(product_id, kind, "purchased", None, False, {"dev": True})


class GooglePlayVerifier(Verifier):  # pragma: no cover - requires Google credentials
    SCOPE = "https://www.googleapis.com/auth/androidpublisher"
    BASE = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
    SUB_STATES = {
        "SUBSCRIPTION_STATE_ACTIVE": "active",
        "SUBSCRIPTION_STATE_IN_GRACE_PERIOD": "grace",
        "SUBSCRIPTION_STATE_ON_HOLD": "on_hold",
        "SUBSCRIPTION_STATE_PAUSED": "on_hold",
        "SUBSCRIPTION_STATE_CANCELED": "canceled",
        "SUBSCRIPTION_STATE_EXPIRED": "expired",
    }

    def __init__(self) -> None:
        s = get_settings()
        if not s.google_service_account_file:
            raise RuntimeError("FM_GOOGLE_SERVICE_ACCOUNT_FILE is required for Google Play verification")
        with open(s.google_service_account_file) as f:
            self._sa = json.load(f)
        self._pkg = s.google_play_package_name
        self._tok: tuple[str, float] | None = None

    def _token(self) -> str:
        if self._tok and self._tok[1] > time.time() + 60:
            return self._tok[0]
        now = int(time.time())
        assertion = jwt.encode(
            {"iss": self._sa["client_email"], "scope": self.SCOPE, "aud": self._sa["token_uri"], "iat": now, "exp": now + 3600},
            self._sa["private_key"], algorithm="RS256",
        )
        r = httpx.post(self._sa["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}, timeout=10)
        r.raise_for_status()
        self._tok = (r.json()["access_token"], now + r.json().get("expires_in", 3600))
        return self._tok[0]

    def _get(self, url: str) -> dict:
        r = httpx.get(url, headers={"Authorization": f"Bearer {self._token()}"}, timeout=15)
        if r.status_code in (400, 404, 410):
            raise AppError(402, "purchase_invalid", "Purchase could not be verified")
        r.raise_for_status()
        return r.json()

    def verify(self, product_id, token, kind):
        if kind == "subscription":
            data = self._get(f"{self.BASE}/{self._pkg}/purchases/subscriptionsv2/tokens/{token}")
            items = [i for i in data.get("lineItems", []) if i.get("productId") == product_id]
            if not items:
                raise AppError(402, "purchase_invalid", "Product mismatch")
            exp = datetime.fromisoformat(items[0]["expiryTime"].replace("Z", "+00:00"))
            status = self.SUB_STATES.get(data.get("subscriptionState"), "expired")
            auto = bool(items[0].get("autoRenewingPlan", {}).get("autoRenewEnabled"))
            return VerifiedPurchase(product_id, kind, status, exp, auto, data,
                                    needs_ack=data.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_PENDING")
        data = self._get(f"{self.BASE}/{self._pkg}/purchases/products/{product_id}/tokens/{token}")
        if data.get("purchaseState") != 0:
            raise AppError(402, "purchase_invalid", "Purchase is not completed")
        return VerifiedPurchase(product_id, kind, "purchased", None, False, data, needs_ack=data.get("acknowledgementState") == 0)

    def acknowledge(self, product_id, token, kind):
        path = "subscriptions" if kind == "subscription" else "products"
        httpx.post(
            f"{self.BASE}/{self._pkg}/purchases/{path}/{product_id}/tokens/{token}:acknowledge",
            headers={"Authorization": f"Bearer {self._token()}"}, json={}, timeout=15,
        )


_verifier: Verifier | None = None


def verifier() -> Verifier:
    global _verifier
    if _verifier is None:
        _verifier = GooglePlayVerifier() if get_settings().billing_mode == "google_play" else DevVerifier()
    return _verifier


def verify_and_apply(db: Session, user_id: uuid.UUID, product_id: str, purchase_token: str, ip: str | None = None) -> dict:
    cfg = get_config(db)
    product = cfg["products"].get(product_id)
    if product is None:
        raise bad_request("unknown_product", "Unknown product")
    if not purchase_token or len(purchase_token) > 512:
        raise bad_request("invalid_token", "Invalid purchase token")
    kind = product["kind"]
    vp = verifier().verify(product_id, purchase_token, kind)
    now = utcnow()

    if kind == "subscription":
        sub = db.scalars(select(Subscription).where(Subscription.purchase_token == purchase_token)).first()
        if sub and sub.user_id != user_id:
            audit(db, "billing.token_reuse", user_id, "subscription", sub.id, ip=ip)
            db.commit()
            raise conflict("purchase_owned", "This purchase belongs to another account")
        if sub is None:
            sub = Subscription(user_id=user_id, purchase_token=purchase_token, started_at=now)
            db.add(sub)
        sub.product_id, sub.tier, sub.status = product_id, product["tier"], vp.status
        sub.expires_at = vp.expires_at or now
        sub.auto_renewing, sub.verified_at, sub.raw = vp.auto_renewing, now, vp.raw
        audit(db, "billing.subscription_verified", user_id, "subscription", sub.id, product=product_id, status=vp.status)
    else:
        if db.scalars(select(Boost).where(Boost.purchase_token == purchase_token)).first():
            raise conflict("already_consumed", "This purchase was already used")
        from app.services.entitlements import active_boost

        current = active_boost(db, user_id, now)
        start = current.ends_at if current else now
        db.add(Boost(user_id=user_id, purchase_token=purchase_token, starts_at=start,
                     ends_at=start + timedelta(minutes=product["boost_minutes"])))
        audit(db, "billing.boost_verified", user_id, "boost", None, product=product_id)
    db.commit()
    if vp.needs_ack:
        try:
            verifier().acknowledge(product_id, purchase_token, kind)
        except Exception:  # retried on next verification / RTDN
            pass
    return {"product_id": product_id, "status": vp.status, "expires_at": vp.expires_at.isoformat() if vp.expires_at else None}


def refresh_from_notification(db: Session, purchase_token: str) -> None:
    """Called for Real-time Developer Notifications: re-verify the token with Google."""
    sub = db.scalars(select(Subscription).where(Subscription.purchase_token == purchase_token)).first()
    if sub is None:
        return
    vp = verifier().verify(sub.product_id, purchase_token, "subscription")
    sub.status, sub.expires_at, sub.auto_renewing = vp.status, vp.expires_at or sub.expires_at, vp.auto_renewing
    sub.verified_at, sub.raw = utcnow(), vp.raw
    db.commit()


def subscription_summary(db: Session, user_id: uuid.UUID) -> list[dict]:
    rows = db.scalars(select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.expires_at.desc())).all()
    return [
        {
            "product_id": s.product_id, "tier": s.tier, "status": s.status, "auto_renewing": s.auto_renewing,
            "expires_at": s.expires_at.astimezone(timezone.utc).isoformat(),
            "manage_url": f"https://play.google.com/store/account/subscriptions?sku={s.product_id}&package={get_settings().google_play_package_name}",
        }
        for s in rows
    ]
