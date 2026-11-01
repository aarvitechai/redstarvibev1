import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.media.schemas import AssetOut
from app.modules.users.schemas import UserBrief


class StoryIn(BaseModel):
    asset_id: uuid.UUID


class StoryOut(BaseModel):
    id: uuid.UUID
    author: UserBrief
    media: AssetOut
    created_at: datetime
    expires_at: datetime
    view_count: int
    viewed: bool = False


class StoryGroup(BaseModel):
    author: UserBrief
    stories: list[StoryOut]
    all_viewed: bool


class HighlightIn(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    story_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class HighlightOut(BaseModel):
    id: uuid.UUID
    title: str
    cover: AssetOut | None
    stories: list[StoryOut]
