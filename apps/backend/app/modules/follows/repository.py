import uuid

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.follows.models import Follow
from app.modules.users.models import User


async def status_of(s: AsyncSession, follower: uuid.UUID, followee: uuid.UUID) -> str | None:
    row = await s.get(Follow, (follower, followee))
    return row.status if row else None


async def statuses(s: AsyncSession, follower: uuid.UUID, followees: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not followees:
        return {}
    q = select(Follow.followee_id, Follow.status).where(Follow.follower_id == follower, Follow.followee_id.in_(followees))
    return {a: b for a, b in (await s.execute(q)).all()}


async def create(s: AsyncSession, follower: uuid.UUID, followee: uuid.UUID, status: str) -> bool:
    res = await s.execute(
        insert(Follow).values(follower_id=follower, followee_id=followee, status=status)
        .on_conflict_do_nothing().returning(Follow.status)
    )
    return res.first() is not None


async def remove(s: AsyncSession, follower: uuid.UUID, followee: uuid.UUID) -> str | None:
    res = await s.execute(
        delete(Follow).where(Follow.follower_id == follower, Follow.followee_id == followee).returning(Follow.status)
    )
    return res.scalar_one_or_none()


async def activate(s: AsyncSession, follower: uuid.UUID, followee: uuid.UUID) -> bool:
    res = await s.execute(
        update(Follow)
        .where(Follow.follower_id == follower, Follow.followee_id == followee, Follow.status == "pending")
        .values(status="active").returning(Follow.follower_id)
    )
    return res.first() is not None


async def accept_all_pending(s: AsyncSession, followee: uuid.UUID) -> None:
    res = await s.execute(
        update(Follow).where(Follow.followee_id == followee, Follow.status == "pending")
        .values(status="active").returning(Follow.follower_id)
    )
    followers = list(res.scalars())
    if followers:
        await s.execute(update(User).where(User.id.in_(followers)).values(following_count=User.following_count + 1))
        await s.execute(
            update(User).where(User.id == followee).values(follower_count=User.follower_count + len(followers))
        )


async def remove_both_directions(s: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
    res = await s.execute(
        delete(Follow).where(
            or_((Follow.follower_id == a) & (Follow.followee_id == b), (Follow.follower_id == b) & (Follow.followee_id == a))
        ).returning(Follow.follower_id, Follow.followee_id, Follow.status)
    )
    return [(x, y) for x, y, st in res.all() if st == "active"]


async def list_followers(s: AsyncSession, user_id: uuid.UUID, cursor: uuid.UUID | None, limit: int) -> list[User]:
    q = select(User).join(Follow, Follow.follower_id == User.id).where(
        Follow.followee_id == user_id, Follow.status == "active"
    )
    if cursor:
        q = q.where(User.id < cursor)
    return list((await s.execute(q.order_by(User.id.desc()).limit(limit))).scalars().unique())


async def list_following(s: AsyncSession, user_id: uuid.UUID, cursor: uuid.UUID | None, limit: int) -> list[User]:
    q = select(User).join(Follow, Follow.followee_id == User.id).where(
        Follow.follower_id == user_id, Follow.status == "active"
    )
    if cursor:
        q = q.where(User.id < cursor)
    return list((await s.execute(q.order_by(User.id.desc()).limit(limit))).scalars().unique())


async def pending_requests(s: AsyncSession, user_id: uuid.UUID) -> list[User]:
    q = select(User).join(Follow, Follow.follower_id == User.id).where(
        Follow.followee_id == user_id, Follow.status == "pending"
    ).order_by(Follow.created_at.desc()).limit(100)
    return list((await s.execute(q)).scalars().unique())


async def active_follower_ids(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    q = select(Follow.follower_id).where(Follow.followee_id == user_id, Follow.status == "active")
    return list((await s.execute(q)).scalars())


async def active_followee_ids(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    q = select(Follow.followee_id).where(Follow.follower_id == user_id, Follow.status == "active")
    return list((await s.execute(q)).scalars())
