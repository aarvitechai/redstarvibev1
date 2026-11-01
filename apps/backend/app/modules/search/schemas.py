from pydantic import BaseModel

from app.modules.posts.schemas import PostOut
from app.modules.users.schemas import UserBrief


class HashtagOut(BaseModel):
    tag: str
    post_count: int


class PlaceOut(BaseModel):
    name: str
    post_count: int


class SearchResults(BaseModel):
    users: list[UserBrief] = []
    hashtags: list[HashtagOut] = []
    places: list[PlaceOut] = []
    posts: list[PostOut] = []
