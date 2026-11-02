import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.media.schemas import AssetOut, MediaEdit, MusicTrack, TextOverlay
from app.modules.users.schemas import UserBrief


class PostCreate(BaseModel):
    asset_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    caption: str = Field("", max_length=2200)
    location: str | None = Field(None, max_length=120)
    visibility: Literal["public", "followers"] = "public"
    is_reel: bool = False
    alt_texts: list[str | None] | None = None
    text_overlays: list[TextOverlay | None] | None = Field(None, max_length=10)  # same order as asset_ids
    tagged_usernames: list[str] = Field(default_factory=list, max_length=20)
    media_edits: list[MediaEdit | None] | None = Field(None, max_length=10)  # same order as asset_ids
    collab_username: str | None = Field(None, max_length=60)
    is_capsule: bool = False
    music: MusicTrack | None = None
    draft: bool = False
    scheduled_at: datetime | None = None


class PostUpdate(BaseModel):
    caption: str | None = Field(None, max_length=2200)
    location: str | None = Field(None, max_length=120)
    visibility: Literal["public", "followers"] | None = None


class PostOut(BaseModel):
    id: uuid.UUID
    author: UserBrief
    caption: str
    location: str | None
    visibility: str
    status: str
    is_reel: bool
    media: list[AssetOut]
    tagged: list[UserBrief] = []
    collaborator: UserBrief | None = None
    pinned: bool = False
    is_capsule: bool = False
    music: str | None = None
    like_count: int
    comment_count: int
    view_count: int
    save_count: int
    created_at: datetime
    scheduled_at: datetime | None = None
    liked: bool = False
    saved: bool = False
    is_own: bool = False


class LikeResult(BaseModel):
    liked: bool
    like_count: int


class CapsuleTeaser(BaseModel):
    count: int
    next_unlock_at: datetime | None


class ViewResult(BaseModel):
    view_count: int
    counted: bool


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str


class SaveIn(BaseModel):
    collection_id: uuid.UUID | None = None


class Insights(BaseModel):
    post_id: uuid.UUID
    views: int
    likes: int
    comments: int
    saves: int
    engagement_rate: float
