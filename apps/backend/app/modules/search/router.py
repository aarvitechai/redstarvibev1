from fastapi import APIRouter, Query

from app.api.deps import Db, OptionalUser
from app.core.pagination import Page
from app.core.rate_limit import hit
from app.modules.posts.schemas import PostOut
from app.modules.search import service
from app.modules.search.schemas import SearchResults

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResults)
async def search(viewer: OptionalUser, s: Db, q: str = Query(max_length=100)) -> SearchResults:
    return await service.search(s, viewer, q)


@router.get("/search/images", response_model=list[PostOut])
async def images(viewer: OptionalUser, s: Db, q: str = Query(min_length=2, max_length=200)) -> list[PostOut]:
    if viewer:
        await hit(f"imgsearch:user:{viewer.id}", 60, 60)
    return await service.image_search(s, viewer, q)


@router.get("/hashtags/{tag}/posts", response_model=Page[PostOut])
async def tag_posts(
    tag: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(24, ge=1, le=48)
) -> Page[PostOut]:
    return await service.tag_page(s, viewer, tag, cursor, limit)


@router.get("/places/{place}/posts", response_model=Page[PostOut])
async def place_posts(
    place: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(24, ge=1, le=48)
) -> Page[PostOut]:
    return await service.place_page(s, viewer, place, cursor, limit)
