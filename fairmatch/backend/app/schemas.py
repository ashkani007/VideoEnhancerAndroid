import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

GENDERS = {"woman", "man", "nonbinary", "other"}
INTENTS = {"long_term", "long_term_open_short", "short_term_open_long", "short_term", "friendship_first", "figuring_out"}


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    date_of_birth: date
    accept_terms: bool
    accept_privacy: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(max_length=200)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID


class Prompt(BaseModel):
    q: str = Field(max_length=120)
    a: str = Field(max_length=300)


class ProfileIn(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=40)
    bio: str | None = Field(default=None, max_length=600)
    gender: str | None = Field(default=None, max_length=32)
    show_gender: bool | None = None
    interested_in: list[str] | None = Field(default=None, max_length=5)
    relationship_intent: str | None = None
    interests: list[str] | None = Field(default=None, max_length=15)
    values: list[str] | None = Field(default=None, max_length=10)
    lifestyle: dict[str, str] | None = None
    communication: dict[str, str] | None = None
    dealbreakers: dict[str, bool] | None = None
    prompts: list[Prompt] | None = Field(default=None, max_length=3)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    city_label: str | None = Field(default=None, max_length=80)
    age_min: int | None = Field(default=None, ge=18, le=99)
    age_max: int | None = Field(default=None, ge=18, le=99)
    max_distance_km: int | None = Field(default=None, ge=1, le=500)
    show_distance: bool | None = None
    read_receipts: bool | None = None
    ai_processing_consent: bool | None = None
    allow_ai_on_my_profile: bool | None = None
    discoverable: bool | None = None

    @field_validator("gender")
    @classmethod
    def _gender(cls, v):
        if v is not None and v not in GENDERS:
            raise ValueError("unsupported gender value")
        return v

    @field_validator("interested_in")
    @classmethod
    def _interested(cls, v):
        if v is not None and any(x not in GENDERS | {"everyone"} for x in v):
            raise ValueError("unsupported preference value")
        return v

    @field_validator("relationship_intent")
    @classmethod
    def _intent(cls, v):
        if v is not None and v not in INTENTS:
            raise ValueError("unsupported relationship intent")
        return v

    @field_validator("interests", "values")
    @classmethod
    def _tags(cls, v):
        if v is None:
            return v
        return [x.strip()[:40] for x in v if x and x.strip()]


class SelectIn(BaseModel):
    pair_id: uuid.UUID
    candidate_id: uuid.UUID


class RespondIn(BaseModel):
    accept: bool


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    client_message_id: str = Field(min_length=1, max_length=64)


class ReadIn(BaseModel):
    up_to_id: int


class ReportIn(BaseModel):
    user_id: uuid.UUID
    reason: str
    details: str = Field(default="", max_length=2000)
    block: bool = True


class BlockIn(BaseModel):
    user_id: uuid.UUID


class PurchaseIn(BaseModel):
    product_id: str = Field(max_length=80)
    purchase_token: str = Field(max_length=512)


class RephraseIn(BaseModel):
    draft: str = Field(min_length=1, max_length=1000)


class DeviceIn(BaseModel):
    token: str = Field(max_length=512)
    platform: Literal["android", "ios", "web"] = "android"


class ModerationIn(BaseModel):
    user_id: uuid.UUID
    report_id: uuid.UUID | None = None
    action: str
    note: str = Field(default="", max_length=500)


class ConsentIn(BaseModel):
    kind: Literal["sensitive_data", "ai_processing", "marketing"]
    granted: bool
