"""SQLAlchemy ORM models. PostgreSQL is the authoritative source of truth."""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"  # hidden from discovery pending moderation
    SUSPENDED = "suspended"
    BANNED = "banned"
    PENDING_DELETION = "pending_deletion"
    DELETED = "deleted"


class Role(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class InterestState(str, enum.Enum):
    """Interest lifecycle. PROPOSED/SELECTED describe a candidate inside a presented pair
    (stored on pair_candidates); the remaining states describe an interest request."""

    PROPOSED = "PROPOSED"
    SELECTED = "SELECTED"
    WAITLISTED = "WAITLISTED"
    PENDING = "PENDING"
    MATCHED = "MATCHED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


ACTIVE_INTEREST_STATES = (InterestState.SELECTED.value, InterestState.WAITLISTED.value, InterestState.PENDING.value)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default=UserStatus.ACTIVE.value, index=True)
    role: Mapped[str] = mapped_column(String(16), default=Role.USER.value)
    # self_declared | estimated | document_verified
    age_assurance: Mapped[str] = mapped_column(String(32), default="self_declared")
    # unverified | pending | verified | rejected  (photo/selfie verification)
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    suspicion_score: Mapped[int] = mapped_column(Integer, default=0)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Photo.position"
    )


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(40))
    bio: Mapped[str] = mapped_column(Text, default="")
    # woman | man | nonbinary | other. Nullable only while onboarding is in progress (profile not completed).
    gender: Mapped[str | None] = mapped_column(String(32))
    show_gender: Mapped[bool] = mapped_column(Boolean, default=True)
    interested_in: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    # long_term | long_term_open_short | short_term_open_long | short_term | friendship_first | figuring_out
    relationship_intent: Mapped[str | None] = mapped_column(String(32))
    interests: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    values: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    lifestyle: Mapped[dict] = mapped_column(JSONB, default=dict)
    communication: Mapped[dict] = mapped_column(JSONB, default=dict)
    dealbreakers: Mapped[dict] = mapped_column(JSONB, default=dict)
    prompts: Mapped[list] = mapped_column(JSONB, default=list)
    # Approximate location only (rounded ~1-2 km); never the raw device coordinates.
    approx_lat: Mapped[float | None] = mapped_column(Float)
    approx_lon: Mapped[float | None] = mapped_column(Float)
    city_label: Mapped[str | None] = mapped_column(String(80))
    age_min: Mapped[int] = mapped_column(Integer, default=18)
    age_max: Mapped[int] = mapped_column(Integer, default=99)
    max_distance_km: Mapped[int] = mapped_column(Integer, default=50)
    # Privacy controls
    show_distance: Mapped[bool] = mapped_column(Boolean, default=True)
    read_receipts: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_processing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_ai_on_my_profile: Mapped[bool] = mapped_column(Boolean, default=True)
    discoverable: Mapped[bool] = mapped_column(Boolean, default=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="profile")

    __table_args__ = (
        CheckConstraint("age_min >= 18", name="ck_profile_age_min_adult"),
        CheckConstraint("age_max >= age_min", name="ck_profile_age_range"),
    )


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)
    moderation_status: Mapped[str] = mapped_column(String(16), default="approved")  # pending | approved | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="photos")


class Block(Base):
    __tablename__ = "blocks"

    blocker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reported_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(32))  # fake_profile | harassment | underage | spam | inappropriate | other
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | dismissed | actioned
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    handled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(String(32))


class PairPresentation(Base):
    """A two-choice pair shown to a viewer."""

    __tablename__ = "pair_presentations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    viewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(16), default="open")  # open | chosen | passed | superseded
    chosen_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    candidates: Mapped[list["PairCandidate"]] = relationship(back_populates="pair", cascade="all, delete-orphan", order_by="PairCandidate.slot")


class PairCandidate(Base):
    """One impression of a candidate inside a pair. Also the exposure ledger used for fairness."""

    __tablename__ = "pair_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    pair_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pair_presentations.id", ondelete="CASCADE"), index=True)
    viewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    slot: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default=InterestState.PROPOSED.value)  # PROPOSED | SELECTED | PASSED
    boosted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pair: Mapped[PairPresentation] = relationship(back_populates="candidates")

    __table_args__ = (
        Index("ix_pair_candidates_candidate_time", "candidate_id", "created_at"),
        Index("ix_pair_candidates_viewer_candidate", "viewer_id", "candidate_id"),
    )


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    from_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(16))
    pair_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pair_presentations.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_reason: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        # At most one active interest per ordered pair of users.
        Index(
            "uq_interest_active_pair",
            "from_user_id",
            "to_user_id",
            unique=True,
            postgresql_where=text("state IN ('SELECTED','WAITLISTED','PENDING')"),
        ),
        UniqueConstraint("from_user_id", "idempotency_key", name="uq_interest_idempotency"),
        Index("ix_interest_to_state", "to_user_id", "state"),
        CheckConstraint("from_user_id <> to_user_id", name="ck_interest_not_self"),
    )


class InterestEvent(Base):
    """Append-only state transition history for auditability."""

    __tablename__ = "interest_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    interest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("interests.id", ondelete="CASCADE"), index=True)
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyQuota(Base):
    __tablename__ = "daily_quotas"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    positive_used: Mapped[int] = mapped_column(Integer, default=0)
    boosted_slots: Mapped[int] = mapped_column(Integer, default=0)
    total_slots: Mapped[int] = mapped_column(Integer, default=0)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_low_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user_high_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(16), default="active")  # active | unmatched | blocked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_match_pair"),
        CheckConstraint("user_low_id < user_high_id", name="ck_match_ordered"),
    )

    def other(self, user_id: uuid.UUID) -> uuid.UUID:
        return self.user_high_id if user_id == self.user_low_id else self.user_low_id

    def includes(self, user_id: uuid.UUID) -> bool:
        return user_id in (self.user_low_id, self.user_high_id)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    client_message_id: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("sender_id", "client_message_id", name="uq_message_client_id"),
        Index("ix_messages_match_id_id", "match_id", "id"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(16), default="google_play")
    product_id: Mapped[str] = mapped_column(String(80))
    tier: Mapped[str] = mapped_column(String(16))
    purchase_token: Mapped[str] = mapped_column(String(512), unique=True)
    status: Mapped[str] = mapped_column(String(16))  # active | grace | on_hold | canceled | expired | revoked
    auto_renewing: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)


class Boost(Base):
    __tablename__ = "boosts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purchase_token: Mapped[str] = mapped_column(String(512), unique=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # terms | privacy | sensitive_data | ai_processing | marketing
    granted: Mapped[bool] = mapped_column(Boolean)
    version: Mapped[str] = mapped_column(String(16), default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    token: Mapped[str] = mapped_column(String(512), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(16), default="android")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppConfigEntry(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
