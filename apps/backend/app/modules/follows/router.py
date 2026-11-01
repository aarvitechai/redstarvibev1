import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser, Db, OptionalUser
from app.core.errors import forbidden
from app.core.pagination import Page, encode_cursor, id_cursor
from app.modules.follows import repository as repo
from app.modules.follows import service
from app.modules.users import service as users
from app.modules.users.schemas import UserBrief

router = APIRouter(tags=["follows"])


class FollowResult(BaseModel):
    status: str


@router.post("/users/{username}/follow", response_model=FollowResult)
async def follow(username: str, me: CurrentUser, s: Db) -> FollowResult:
    return FollowResult(status=await service.follow(s, me, username))


@router.delete("/users/{username}/follow", status_code=204)
async def unfollow(username: str, me: CurrentUser, s: Db) -> None:
    await service.unfollow(s, me, username)


@router.delete("/users/{username}/follower", status_code=204)
async def remove_follower(username: str, me: CurrentUser, s: Db) -> None:
    await service.remove_follower(s, me, username)


async def _people(s, viewer, username, cursor, limit, fetch) -> Page[UserBrief]:  # type: ignore[no-untyped-def]
    user = await users.get_visible_user(s, viewer, username)
    if not await users.can_view_content_of(s, viewer, user):
        raise forbidden("This account is private")
    rows = await fetch(s, user.id, id_cursor(cursor), limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(items=[users.brief(u) for u in rows], next_cursor=encode_cursor(rows[-1].id) if more else None)


@router.get("/users/{username}/followers", response_model=Page[UserBrief])
async def followers(
    username: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(30, le=100, ge=1)
) -> Page[UserBrief]:
    return await _people(s, viewer, username, cursor, limit, repo.list_followers)


@router.get("/users/{username}/following", response_model=Page[UserBrief])
async def following(
    username: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(30, le=100, ge=1)
) -> Page[UserBrief]:
    return await _people(s, viewer, username, cursor, limit, repo.list_following)


@router.get("/follow-requests", response_model=list[UserBrief])
async def requests(me: CurrentUser, s: Db) -> list[UserBrief]:
    return [users.brief(u) for u in await repo.pending_requests(s, me.id)]


@router.post("/follow-requests/{follower_id}/accept", status_code=204)
async def accept(follower_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.accept(s, me, follower_id)


@router.post("/follow-requests/{follower_id}/reject", status_code=204)
async def reject(follower_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.reject(s, me, follower_id)
