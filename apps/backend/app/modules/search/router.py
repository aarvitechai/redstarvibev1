import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import Db, OptionalUser
from app.core.pagination import Page
from app.core.rate_limit import ip_limit
from app.modules.posts.schemas import PostOut
from app.modules.search import service
from app.modules.search.schemas import HashtagOut, PlaceOut, SearchSuggest
from app.modules.users.schemas import UserBrief

router = APIRouter(tags=["search"])
limited = [Depends(ip_limit("search", 180, 60))]


@router.get(
    "/search", dependencies=limited,
    response_model=Page[PostOut] | Page[UserBrief] | Page[HashtagOut] | Page[PlaceOut],
)
async def search(
    viewer: OptionalUser, s: Db, q: str = Query(max_length=200),
    type: Literal["posts", "users", "tags", "places"] = "posts",  # noqa: A002
    cursor: str | None = None, limit: int = Query(24, ge=1, le=48),
) -> Page[PostOut] | Page[UserBrief] | Page[HashtagOut] | Page[PlaceOut]:
    if type == "users":
        return await service.users_page(s, viewer, q, cursor, limit)
    if type == "tags":
        return await service.tags_page(s, viewer, q, cursor, limit)
    if type == "places":
        return await service.places_page(s, viewer, q, cursor, limit)
    return await service.posts_page(s, viewer, q, cursor, limit)


@router.get("/search/suggest", response_model=SearchSuggest, dependencies=limited)
async def suggest(viewer: OptionalUser, s: Db, q: str = Query(max_length=200)) -> SearchSuggest:
    return await service.suggest(s, viewer, q)


@router.get("/posts/{post_id}/similar", response_model=list[PostOut])
async def similar(post_id: uuid.UUID, viewer: OptionalUser, s: Db, limit: int = Query(12, ge=1, le=24)) -> list[PostOut]:
    return await service.similar_posts(s, viewer, post_id, limit)


@router.get("/hashtags/{tag}/posts", response_model=Page[PostOut])
async def tag_posts(
    tag: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(24, ge=1, le=48),
    sort: Literal["recent", "top"] = "recent",
) -> Page[PostOut]:
    if sort == "top":
        return await service.tag_top_page(s, viewer, tag, cursor, limit)
    return await service.tag_page(s, viewer, tag, cursor, limit)


@router.get("/places/{place}/posts", response_model=Page[PostOut])
async def place_posts(
    place: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(24, ge=1, le=48)
) -> Page[PostOut]:
    return await service.place_page(s, viewer, place, cursor, limit)
