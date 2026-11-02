import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator


class UserBrief(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None = None
    verified: bool = False


class ProfileOut(UserBrief):
    bio: str
    website: str | None
    is_private: bool
    follower_count: int
    following_count: int
    post_count: int
    is_self: bool = False
    follow_status: str | None = None  # active | pending | None
    follows_you: bool = False
    is_blocked: bool = False
    is_muted: bool = False
    is_restricted: bool = False
    can_view_posts: bool = True
    has_active_story: bool = False


class MeOut(ProfileOut):
    email: str
    role: str
    status: str
    totp_enabled: bool
    delete_after: datetime | None = None
    hidden_words: list[str] = []
    permissions: list[str] = []


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(None, max_length=80)
    bio: str | None = Field(None, max_length=500)
    website: HttpUrl | None = None
    is_private: bool | None = None
    avatar_asset_id: uuid.UUID | None = None
    phone: str | None = Field(None, max_length=20)
    hidden_words: list[Annotated[str, StringConstraints(max_length=50)]] | None = Field(None, max_length=200)

    @field_validator("website")
    @classmethod
    def only_http(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is not None and v.scheme not in {"http", "https"}:
            raise ValueError("must be http or https")
        return v


class DataExport(BaseModel):
    profile: dict[str, object]
    posts: list[dict[str, object]]
    comments: list[dict[str, object]]
    following: list[str]
    followers: list[str]
    saved_post_ids: list[str]
