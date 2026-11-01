from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db, OptionalUser
from app.core.pagination import Page
from app.modules.feed import service
from app.modules.posts.schemas import PostOut

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=Page[PostOut])
async def home(me: CurrentUser, s: Db, cursor: str | None = None, limit: int = Query(10, ge=1, le=30)) -> Page[PostOut]:
    return await service.home_feed(s, me, cursor, limit)


@router.get("/explore", response_model=Page[PostOut])
async def explore(
    viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(24, ge=1, le=48)
) -> Page[PostOut]:
    return await service.explore(s, viewer, cursor, limit)
