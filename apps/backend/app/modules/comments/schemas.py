import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.users.schemas import UserBrief


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2200)
    parent_id: uuid.UUID | None = None


class CommentOut(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    parent_id: uuid.UUID | None
    author: UserBrief
    body: str
    reply_count: int
    held: bool = False
    created_at: datetime
    can_delete: bool = False
