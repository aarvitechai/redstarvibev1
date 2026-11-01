import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.follows.models import Follow
from app.modules.media.models import MediaAsset
from app.modules.users.models import AuditLog, Block, Profile, User


async def by_id(s: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await s.get(User, user_id)


async def by_username(s: AsyncSession, username: str) -> User | None:
    return (await s.execute(select(User).where(User.username == username))).scalars().first()


async def by_usernames(s: AsyncSession, usernames: Sequence[str]) -> list[User]:
    if not usernames:
        return []
    return list((await s.execute(select(User).where(User.username.in_(usernames)))).scalars().unique())


async def by_email(s: AsyncSession, email: str) -> User | None:
    return (await s.execute(select(User).where(User.email == email))).scalars().first()


async def by_ids(s: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    rows = (await s.execute(select(User).where(User.id.in_(set(ids))))).scalars().unique()
    return {u.id: u for u in rows}


async def add_user(s: AsyncSession, user: User, profile: Profile) -> None:
    user.profile = profile
    s.add(user)
    await s.flush()


async def is_blocked_either_way(s: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> bool:
    q = select(Block.blocker_id).where(
        or_((Block.blocker_id == a) & (Block.blocked_id == b), (Block.blocker_id == b) & (Block.blocked_id == a))
    )
    return (await s.execute(q.limit(1))).first() is not None


async def blocked_ids(s: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    q = select(Block.blocked_id).where(Block.blocker_id == user_id).union(
        select(Block.blocker_id).where(Block.blocked_id == user_id)
    )
    return set((await s.execute(q)).scalars())


async def has_blocked(s: AsyncSession, blocker: uuid.UUID, blocked: uuid.UUID) -> bool:
    return await s.get(Block, (blocker, blocked)) is not None


async def add_block(s: AsyncSession, blocker: uuid.UUID, blocked: uuid.UUID) -> None:
    await s.execute(insert(Block).values(blocker_id=blocker, blocked_id=blocked).on_conflict_do_nothing())


async def remove_block(s: AsyncSession, blocker: uuid.UUID, blocked: uuid.UUID) -> None:
    await s.execute(delete(Block).where(Block.blocker_id == blocker, Block.blocked_id == blocked))


async def blocked_list(s: AsyncSession, user_id: uuid.UUID) -> list[User]:
    q = select(User).join(Block, Block.blocked_id == User.id).where(Block.blocker_id == user_id)
    return list((await s.execute(q)).scalars().unique())


async def suggestions(s: AsyncSession, user_id: uuid.UUID, limit: int) -> list[User]:
    followed = select(Follow.followee_id).where(Follow.follower_id == user_id)
    blocked = select(Block.blocked_id).where(Block.blocker_id == user_id).union(
        select(Block.blocker_id).where(Block.blocked_id == user_id)
    )
    q = (
        select(User)
        .where(User.id != user_id, User.status == "active", User.id.not_in(followed), User.id.not_in(blocked))
        .order_by(User.follower_count.desc(), User.id.desc())
        .limit(limit)
    )
    return list((await s.execute(q)).scalars().unique())


async def ready_avatar(s: AsyncSession, asset_id: uuid.UUID, owner_id: uuid.UUID) -> MediaAsset | None:
    asset = await s.get(MediaAsset, asset_id)
    if asset and asset.owner_id == owner_id and asset.status == "ready" and asset.kind == "image":
        return asset
    return None


async def bump_counts(s: AsyncSession, user_id: uuid.UUID, **deltas: int) -> None:
    values: dict[str, Any] = {k: getattr(User, k) + v for k, v in deltas.items()}
    await s.execute(update(User).where(User.id == user_id).values(**values))


async def audit(
    s: AsyncSession, actor: uuid.UUID | None, action: str, target: str | None = None,
    ip: str | None = None, meta: dict[str, Any] | None = None,
) -> None:
    valid_ip = ip if ip and ip != "unknown" else None
    s.add(AuditLog(actor_id=actor, action=action, target=target, ip=valid_ip, meta=meta))


async def schedule_deletion(s: AsyncSession, user: User, days: int = 30) -> None:
    user.status = "deleting"
    user.delete_after = datetime.now(UTC) + timedelta(days=days)


async def users_due_for_purge(s: AsyncSession) -> list[uuid.UUID]:
    q = select(User.id).where(User.status == "deleting", User.delete_after < datetime.now(UTC))
    return list((await s.execute(q)).scalars())


async def purge(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Hard delete. Tables without a foreign key (partitioned ones) are cleared explicitly."""
    from app.ai.models import Embedding
    from app.modules.chat.models import Message
    from app.modules.notifications.models import Notification
    from app.modules.posts.models import Like

    asset_ids = list((await s.execute(select(MediaAsset.id).where(MediaAsset.owner_id == user_id))).scalars())
    await s.execute(delete(Like).where(Like.user_id == user_id))
    await s.execute(delete(Message).where(Message.sender_id == user_id))
    await s.execute(delete(Notification).where(Notification.user_id == user_id))
    await s.execute(delete(Embedding).where(Embedding.owner_id == user_id))
    await s.execute(delete(User).where(User.id == user_id))
    return asset_ids
