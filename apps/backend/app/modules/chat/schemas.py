import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.modules.media.schemas import AssetOut
from app.modules.posts.schemas import PostOut
from app.modules.users.schemas import UserBrief


class ConversationCreate(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=31)
    title: str | None = Field(None, max_length=80)


class MessageIn(BaseModel):
    body: str = Field("", max_length=5000)
    asset_id: uuid.UUID | None = None
    post_id: uuid.UUID | None = None


class ConversationUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class MemberIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)


class TranslateIn(BaseModel):
    language: Literal["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "ur"]


class TranslateOut(BaseModel):
    text: str
    language: str


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    media: AssetOut | None = None
    post_id: uuid.UUID | None = None
    shared_post: PostOut | None = None  # empty when this viewer is not allowed to see the post
    created_at: datetime


class MemberState(BaseModel):
    user: UserBrief
    last_delivered_at: datetime | None
    last_seen_at: datetime | None
    online: bool = False


class ConversationOut(BaseModel):
    id: uuid.UUID
    is_group: bool
    title: str | None
    members: list[MemberState]
    last_message: MessageOut | None = None
    last_message_at: datetime
    unread: int = 0
    my_state: str = "active"
    waiting_for_accept: bool = False
