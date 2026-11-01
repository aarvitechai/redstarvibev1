import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.users.schemas import UserBrief


class CallCreate(BaseModel):
    conversation_id: uuid.UUID
    kind: Literal["audio", "video"]


class CallJoin(BaseModel):
    call_id: uuid.UUID
    room: str
    kind: str
    token: str
    url: str
    can_publish: bool


class LiveCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class LiveOut(BaseModel):
    id: uuid.UUID
    title: str | None
    host: UserBrief
    room: str
