import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, conflict, not_found
from app.core.events import emit
from app.modules.follows import repository as repo
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User


async def follow(s: AsyncSession, me: User, username: str) -> str:
    other = await user_service.get_visible_user(s, me, username)
    if other.id == me.id:
        raise bad_request("invalid_target", "You cannot follow yourself")
    if await users.is_blocked_either_way(s, me.id, other.id):
        raise conflict("blocked", "You cannot follow this account")
    status = "pending" if other.is_private else "active"
    created = await repo.create(s, me.id, other.id, status)
    if not created:
        return await repo.status_of(s, me.id, other.id) or status
    if status == "active":
        await users.bump_counts(s, me.id, following_count=1)
        await users.bump_counts(s, other.id, follower_count=1)
    await s.commit()
    await emit("user.followed", follower_id=me.id, followee_id=other.id, status=status)
    return status


async def unfollow(s: AsyncSession, me: User, username: str) -> None:
    other = await users.by_username(s, username)
    if other is None:
        raise not_found("User")
    previous = await repo.remove(s, me.id, other.id)
    if previous == "active":
        await users.bump_counts(s, me.id, following_count=-1)
        await users.bump_counts(s, other.id, follower_count=-1)
    await s.commit()
    if previous == "active":
        await emit("user.unfollowed", follower_id=me.id, followee_id=other.id)


async def accept(s: AsyncSession, me: User, follower_id: uuid.UUID) -> None:
    if not await repo.activate(s, follower_id, me.id):
        raise not_found("Follow request")
    await users.bump_counts(s, follower_id, following_count=1)
    await users.bump_counts(s, me.id, follower_count=1)
    await s.commit()
    await emit("user.follow_accepted", follower_id=follower_id, followee_id=me.id)


async def reject(s: AsyncSession, me: User, follower_id: uuid.UUID) -> None:
    if await repo.status_of(s, follower_id, me.id) != "pending":
        raise not_found("Follow request")
    await repo.remove(s, follower_id, me.id)
    await s.commit()


async def remove_follower(s: AsyncSession, me: User, username: str) -> None:
    other = await users.by_username(s, username)
    if other is None:
        raise not_found("User")
    if await repo.remove(s, other.id, me.id) == "active":
        await users.bump_counts(s, other.id, following_count=-1)
        await users.bump_counts(s, me.id, follower_count=-1)
    await s.commit()
    await emit("user.unfollowed", follower_id=other.id, followee_id=me.id)
