import uuid

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db, OptionalUser
from app.core.pagination import Page, id_cursor
from app.modules.communities import service
from app.modules.communities.service import CommunityIn, CommunityOut, CommunityPostIn, CommunityPostOut
from app.modules.users.schemas import UserBrief

router = APIRouter(tags=["communities"])


@router.post("/communities", response_model=CommunityOut, status_code=201)
async def create(data: CommunityIn, me: CurrentUser, s: Db) -> CommunityOut:
    return await service.create(s, me, data)


@router.get("/communities", response_model=list[CommunityOut])
async def browse(viewer: OptionalUser, s: Db, q: str = Query("", max_length=80), mine: bool = False) -> list[CommunityOut]:
    return await service.browse(s, viewer, q.strip(), mine)


@router.get("/communities/{slug}", response_model=CommunityOut)
async def get(slug: str, viewer: OptionalUser, s: Db) -> CommunityOut:
    return await service.get(s, viewer, slug)


@router.delete("/communities/{slug}", status_code=204)
async def delete_community(slug: str, me: CurrentUser, s: Db) -> None:
    await service.delete_community(s, me, slug)


@router.post("/communities/{slug}/join", response_model=CommunityOut)
async def join(slug: str, me: CurrentUser, s: Db) -> CommunityOut:
    return await service.join(s, me, slug)


@router.post("/communities/{slug}/leave", response_model=CommunityOut)
async def leave(slug: str, me: CurrentUser, s: Db) -> CommunityOut:
    return await service.leave(s, me, slug)


@router.get("/communities/{slug}/members", response_model=list[UserBrief])
async def members(slug: str, _: OptionalUser, s: Db) -> list[UserBrief]:
    return await service.members(s, slug)


@router.delete("/communities/{slug}/members/{user_id}", status_code=204)
async def remove_member(slug: str, user_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.remove_member(s, me, slug, user_id)


@router.get("/communities/{slug}/posts", response_model=Page[CommunityPostOut])
async def list_posts(
    slug: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(20, ge=1, le=50)
) -> Page[CommunityPostOut]:
    return await service.list_posts(s, viewer, slug, id_cursor(cursor), limit)


@router.post("/communities/{slug}/posts", response_model=CommunityPostOut, status_code=201)
async def add_post(slug: str, data: CommunityPostIn, me: CurrentUser, s: Db) -> CommunityPostOut:
    return await service.add_post(s, me, slug, data)


@router.delete("/community-posts/{post_id}", status_code=204)
async def delete_post(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.delete_post(s, me, post_id)
