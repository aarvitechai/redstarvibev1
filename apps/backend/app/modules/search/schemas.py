from pydantic import BaseModel

from app.modules.users.schemas import UserBrief


class HashtagOut(BaseModel):
    tag: str
    post_count: int


class PlaceOut(BaseModel):
    name: str
    post_count: int


class SearchSuggest(BaseModel):
    users: list[UserBrief]
    tags: list[HashtagOut]
