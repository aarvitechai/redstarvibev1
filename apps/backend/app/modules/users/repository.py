import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.follows.models import Follow
from app.modules.media.models import MediaAsset
from app.modules.users.models import AuditLog, Block, Profile, User, UserLimit


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


async def limit_ids(s: AsyncSession, user_id: uuid.UUID, kind: str) -> set[uuid.UUID]:
    q = select(UserLimit.target_id).where(UserLimit.user_id == user_id, UserLimit.kind == kind)
    return set((await s.execute(q)).scalars())


async def has_limit(s: AsyncSession, user_id: uuid.UUID, target_id: uuid.UUID, kind: str) -> bool:
    return await s.get(UserLimit, (user_id, target_id, kind)) is not None


async def add_limit(s: AsyncSession, user_id: uuid.UUID, target_id: uuid.UUID, kind: str) -> None:
    await s.execute(insert(UserLimit).values(user_id=user_id, target_id=target_id, kind=kind).on_conflict_do_nothing())


async def remove_limit(s: AsyncSession, user_id: uuid.UUID, target_id: uuid.UUID, kind: str) -> None:
    await s.execute(delete(UserLimit).where(
        UserLimit.user_id == user_id, UserLimit.target_id == target_id, UserLimit.kind == kind
    ))


async def limited_list(s: AsyncSession, user_id: uuid.UUID, kind: str) -> list[User]:
    q = select(User).join(UserLimit, UserLimit.target_id == User.id).where(UserLimit.user_id == user_id, UserLimit.kind == kind)
    return list((await s.execute(q.order_by(UserLimit.created_at.desc()))).scalars().unique())


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


@dataclass
class PurgeResult:
    asset_ids: list[uuid.UUID]
    touched_post_ids: list[uuid.UUID]  # other people's posts whose counters changed, so their cache is stale


async def interests_of(s: AsyncSession, user_id: uuid.UUID) -> list[str]:
    return list((await s.execute(select(Profile.interests).where(Profile.user_id == user_id))).scalar_one_or_none() or [])


async def set_interests(s: AsyncSession, user_id: uuid.UUID, interests: list[str]) -> None:
    await s.execute(update(Profile).where(Profile.user_id == user_id).values(interests=interests))


async def purge(s: AsyncSession, user_id: uuid.UUID) -> PurgeResult:
    """Hard delete that leaves everyone else's counters correct.

    Tables without a foreign key (partitioned ones) are cleared explicitly.
    """
    from app.ai.models import Embedding
    from app.modules.chat.models import Message
    from app.modules.comments.models import Comment
    from app.modules.notifications.models import Notification
    from app.modules.posts.models import Hashtag, Like, Post, PostHashtag, Save

    asset_ids = list((await s.execute(select(MediaAsset.id).where(MediaAsset.owner_id == user_id))).scalars())
    own_posts = select(Post.id).where(Post.author_id == user_id)

    followees = select(Follow.followee_id).where(Follow.follower_id == user_id, Follow.status == "active")
    followers = select(Follow.follower_id).where(Follow.followee_id == user_id, Follow.status == "active")
    await s.execute(update(User).where(User.id.in_(followees)).values(follower_count=func.greatest(User.follower_count - 1, 0)))
    await s.execute(update(User).where(User.id.in_(followers)).values(following_count=func.greatest(User.following_count - 1, 0)))

    tags = await s.execute(
        select(PostHashtag.tag, func.count()).where(PostHashtag.post_id.in_(own_posts)).group_by(PostHashtag.tag)
    )
    for tag, count in tags.all():
        await s.execute(update(Hashtag).where(Hashtag.tag == tag).values(post_count=func.greatest(Hashtag.post_count - count, 0)))

    touched: set[uuid.UUID] = set()
    liked = list((await s.execute(
        delete(Like).where(Like.user_id == user_id, Like.post_id.not_in(own_posts)).returning(Like.post_id)
    )).scalars())
    if liked:
        touched.update(liked)
        await s.execute(update(Post).where(Post.id.in_(liked)).values(like_count=func.greatest(Post.like_count - 1, 0)))
    saved = list((await s.execute(
        select(Save.post_id).where(Save.user_id == user_id, Save.post_id.not_in(own_posts))
    )).scalars())
    if saved:
        touched.update(saved)
        await s.execute(update(Post).where(Post.id.in_(saved)).values(save_count=func.greatest(Post.save_count - 1, 0)))
    commented = await s.execute(
        select(Comment.post_id, func.count())
        .where(
            Comment.author_id == user_id, Comment.post_id.not_in(own_posts), Comment.deleted_at.is_(None),
            Comment.held.is_(False),
        )
        .group_by(Comment.post_id)
    )
    for post_id, count in commented.all():
        touched.add(post_id)
        await s.execute(update(Post).where(Post.id == post_id).values(comment_count=func.greatest(Post.comment_count - count, 0)))

    await s.execute(delete(Like).where(Like.post_id.in_(own_posts)))  # likes have no foreign key to posts
    await s.execute(delete(Like).where(Like.user_id == user_id))
    await s.execute(delete(Message).where(Message.sender_id == user_id))
    await s.execute(delete(Notification).where(Notification.user_id == user_id))
    await s.execute(delete(Embedding).where(Embedding.owner_id == user_id))
    await s.execute(delete(User).where(User.id == user_id))
    return PurgeResult(asset_ids, list(touched))
