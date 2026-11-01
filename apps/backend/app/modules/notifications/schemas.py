import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.users.schemas import UserBrief


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    actor: UserBrief | None
    entity_id: uuid.UUID | None
    read: bool
    created_at: datetime


class UnreadCount(BaseModel):
    count: int


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=300)
    auth: str = Field(max_length=100)


class PushSubscribe(BaseModel):
    endpoint: str = Field(max_length=2000, pattern=r"^https://")
    keys: PushKeys


class PushPublicKey(BaseModel):
    public_key: str | None
