import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.media.schemas import AssetOut
from app.modules.users.schemas import UserBrief


class ConversationCreate(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=31)
    title: str | None = Field(None, max_length=80)


class MessageIn(BaseModel):
    body: str = Field("", max_length=5000)
    asset_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    media: AssetOut | None = None
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
