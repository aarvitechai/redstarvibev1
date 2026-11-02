import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.modules.media.schemas import AssetOut
from app.modules.users.schemas import UserBrief

Emoji = Literal["❤️", "🔥", "😂", "😮", "😢", "👏"]
Frame = Literal["diwali", "holi", "eid", "christmas"]


class StickerIn(BaseModel):
    kind: Literal["poll", "quiz"]
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    options: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]] = Field(
        min_length=2, max_length=4
    )
    correct: int | None = None

    @model_validator(mode="after")
    def _correct_matches_kind(self) -> "StickerIn":
        if self.kind == "quiz" and (self.correct is None or not 0 <= self.correct < len(self.options)):
            raise ValueError("a quiz needs one correct option")
        if self.kind == "poll" and self.correct is not None:
            raise ValueError("a poll has no correct option")
        return self


class StoryIn(BaseModel):
    asset_id: uuid.UUID
    audience: Literal["everyone", "close_friends"] = "everyone"
    frame: Frame | None = None
    sticker: StickerIn | None = None


class StickerOut(BaseModel):
    kind: str
    question: str
    options: list[str]
    counts: list[int] | None = None  # shown once the viewer has answered, and always to the author
    my_answer: int | None = None
    correct: int | None = None  # a quiz keeps this secret until the viewer has answered


class ReactIn(BaseModel):
    emoji: Emoji


class AnswerIn(BaseModel):
    option: int = Field(ge=0, le=3)


class CloseFriendIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)


class StoryActivity(BaseModel):
    user: UserBrief
    reaction: str | None = None
    answer: int | None = None


class StoryOut(BaseModel):
    id: uuid.UUID
    author: UserBrief
    media: AssetOut
    created_at: datetime
    expires_at: datetime
    view_count: int
    viewed: bool = False
    audience: str = "everyone"
    frame: str | None = None
    sticker: StickerOut | None = None
    my_reaction: str | None = None


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
