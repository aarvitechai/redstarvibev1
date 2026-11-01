from fastapi import APIRouter, Query

from app.api.deps import Db, OptionalUser
from app.core.pagination import Page
from app.modules.posts.schemas import PostOut
from app.modules.reels import service

router = APIRouter(tags=["reels"])


@router.get("/reels", response_model=Page[PostOut])
async def reels(
    viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(6, ge=1, le=20)
) -> Page[PostOut]:
    return await service.reels_page(s, viewer, cursor, limit)
