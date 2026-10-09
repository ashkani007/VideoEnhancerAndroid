from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import get_settings


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PREVIEW_READY = "PREVIEW_READY"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.UPLOADING.value, index=True)
    phase: Mapped[str] = mapped_column(String(10), default="preview")  # preview | full
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    stage: Mapped[str] = mapped_column(String(120), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Explicit consent captured from the client (audit trail).
    consent_granted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    consent_text_version: Mapped[str] = mapped_column(String(40))

    file_name: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    received_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    fps: Mapped[float] = mapped_column(Float)
    duration_ms: Mapped[int] = mapped_column(BigInteger)
    layout: Mapped[str] = mapped_column(String(20))
    projection: Mapped[str] = mapped_column(String(20))
    out_width: Mapped[int] = mapped_column(Integer)
    out_height: Mapped[int] = mapped_column(Integer)
    denoise: Mapped[bool] = mapped_column(Boolean, default=True)
    sharpen_amount: Mapped[float] = mapped_column(Float, default=0.0)
    preview_start_ms: Mapped[int] = mapped_column(BigInteger, default=0)

    source_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preview_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    probe: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


_engine = None
_Session = None


def engine():
    global _engine, _Session
    if _engine is None:
        url = get_settings().database_url
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_engine(url, **kwargs)
        _Session = sessionmaker(_engine, expire_on_commit=False)
        Base.metadata.create_all(_engine)
    return _engine


def session():
    engine()
    return _Session()


def reset_for_tests() -> None:
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None
