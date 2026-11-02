from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db, OptionalUser
from app.core.errors import forbidden
from app.core.pagination import Page, encode_cursor, id_cursor
from app.modules.follows import repository as follows
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.modules.posts.schemas import CapsuleTeaser, PostOut
from app.modules.users import repository as repo
from app.modules.users import service
from app.modules.users.schemas import DataExport, MeOut, ProfileOut, ProfileUpdate, UserBrief

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=MeOut)
async def update_me(data: ProfileUpdate, me: CurrentUser, s: Db) -> MeOut:
    return await service.update_profile(s, me, data)


@router.get("/me/export", response_model=DataExport)
async def export_me(me: CurrentUser, s: Db) -> DataExport:
    return await posts.export_user_data(s, me)


@router.delete("/me", status_code=204)
async def delete_me(me: CurrentUser, s: Db) -> None:
    await service.request_deletion(s, me)


@router.post("/me/restore", status_code=204)
async def restore_me(me: CurrentUser, s: Db) -> None:
    await service.cancel_deletion(s, me)


@router.get("/suggestions", response_model=list[UserBrief])
async def suggestions(me: CurrentUser, s: Db, limit: int = Query(8, ge=1, le=30)) -> list[UserBrief]:
    return [service.brief(u) for u in await repo.suggestions(s, me.id, limit)]


@router.get("/me/blocked", response_model=list[UserBrief])
async def blocked(me: CurrentUser, s: Db) -> list[UserBrief]:
    return [service.brief(u) for u in await repo.blocked_list(s, me.id)]


@router.get("/me/muted", response_model=list[UserBrief])
async def muted(me: CurrentUser, s: Db) -> list[UserBrief]:
    return [service.brief(u) for u in await repo.limited_list(s, me.id, "mute")]


@router.get("/me/restricted", response_model=list[UserBrief])
async def restricted(me: CurrentUser, s: Db) -> list[UserBrief]:
    return [service.brief(u) for u in await repo.limited_list(s, me.id, "restrict")]


@router.get("/{username}", response_model=ProfileOut)
async def profile(username: str, viewer: OptionalUser, s: Db) -> ProfileOut:
    return await service.profile_out(s, viewer, await service.get_visible_user(s, viewer, username))


@router.get("/{username}/posts", response_model=Page[PostOut])
async def user_posts(
    username: str, viewer: OptionalUser, s: Db, cursor: str | None = None,
    limit: int = Query(18, ge=1, le=48), reels: bool = False,
) -> Page[PostOut]:
    user = await service.get_visible_user(s, viewer, username)
    if not await service.can_view_content_of(s, viewer, user):
        raise forbidden("This account is private")
    following = bool(viewer and await follows.status_of(s, viewer.id, user.id) == "active")
    include_followers_only = following or bool(viewer and viewer.id == user.id)
    ids = await post_repo.author_post_ids(s, user.id, include_followers_only, id_cursor(cursor), limit + 1, reels)
    more = len(ids) > limit
    ids = ids[:limit]
    next_cursor = encode_cursor(ids[-1]) if more else None
    if not cursor and not reels:
        ids = [*await post_repo.pinned_post_ids(s, user.id, include_followers_only), *ids]
    return Page(items=await posts.hydrate(s, viewer, ids), next_cursor=next_cursor)


@router.get("/{username}/capsules", response_model=CapsuleTeaser)
async def capsules(username: str, viewer: OptionalUser, s: Db) -> CapsuleTeaser:
    return await posts.capsule_teaser(s, viewer, username)


@router.get("/{username}/tagged", response_model=Page[PostOut])
async def tagged_posts(
    username: str, viewer: OptionalUser, s: Db, cursor: str | None = None, limit: int = Query(18, ge=1, le=48),
) -> Page[PostOut]:
    user = await service.get_visible_user(s, viewer, username)
    ids = await post_repo.tagged_post_ids(s, user.id, viewer.id if viewer else None, id_cursor(cursor), limit + 1)
    more = len(ids) > limit
    ids = ids[:limit]
    return Page(items=await posts.hydrate(s, viewer, ids), next_cursor=encode_cursor(ids[-1]) if more else None)


@router.post("/{username}/mute", status_code=204)
async def mute(username: str, me: CurrentUser, s: Db) -> None:
    await service.set_limit(s, me, username, "mute", True)


@router.delete("/{username}/mute", status_code=204)
async def unmute(username: str, me: CurrentUser, s: Db) -> None:
    await service.set_limit(s, me, username, "mute", False)


@router.post("/{username}/restrict", status_code=204)
async def restrict(username: str, me: CurrentUser, s: Db) -> None:
    await service.set_limit(s, me, username, "restrict", True)


@router.delete("/{username}/restrict", status_code=204)
async def unrestrict(username: str, me: CurrentUser, s: Db) -> None:
    await service.set_limit(s, me, username, "restrict", False)


@router.post("/{username}/block", status_code=204)
async def block(username: str, me: CurrentUser, s: Db) -> None:
    await service.block(s, me, username)


@router.delete("/{username}/block", status_code=204)
async def unblock(username: str, me: CurrentUser, s: Db) -> None:
    await service.unblock(s, me, username)
