import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import Embedding
from app.modules.follows.models import Follow
from app.modules.posts.models import Like, Post, PostCollab
from app.modules.posts.repository import visible_clause
from app.modules.users.models import User


async def recent_for_rebuild(s: AsyncSession, user_id: uuid.UUID, limit: int) -> list[uuid.UUID]:
    """Newest posts from accounts the user follows, plus their own. Excludes celebrities' fan-out-on-read."""
    followed = select(Follow.followee_id).where(Follow.follower_id == user_id, Follow.status == "active")
    collabs = select(PostCollab.post_id).where(PostCollab.status == "accepted", PostCollab.user_id.in_(followed))
    q = (
        select(Post.id).join(User, User.id == Post.author_id)
        .where(visible_clause(user_id), (Post.author_id.in_(followed)) | (Post.author_id == user_id) | Post.id.in_(collabs))
        .order_by(Post.id.desc()).limit(limit)
    )
    return list((await s.execute(q)).scalars())


async def celebrity_post_ids(
    s: AsyncSession, user_id: uuid.UUID, threshold: int, before: uuid.UUID | None, limit: int
) -> list[uuid.UUID]:
    q = (
        select(Post.id).join(User, User.id == Post.author_id)
        .join(Follow, and_(Follow.followee_id == User.id, Follow.follower_id == user_id, Follow.status == "active"))
        .where(User.follower_count >= threshold, visible_clause(user_id))
    )
    if before:
        q = q.where(Post.id < before)
    return list((await s.execute(q.order_by(Post.id.desc()).limit(limit))).scalars())


async def explore_ids(
    s: AsyncSession, viewer: uuid.UUID | None, cursor: uuid.UUID | None, limit: int, reels_only: bool = False
) -> list[uuid.UUID]:
    q = (
        select(Post.id).join(User, User.id == Post.author_id)
        .where(visible_clause(viewer), Post.visibility == "public", User.is_private.is_(False))
    )
    if viewer:
        followed = select(Follow.followee_id).where(Follow.follower_id == viewer)
        if not reels_only:
            q = q.where(Post.author_id != viewer, Post.author_id.not_in(followed))
    if reels_only:
        q = q.where(Post.is_reel.is_(True))
    if cursor:
        q = q.where(Post.id < cursor)
    return list((await s.execute(q.order_by(Post.id.desc()).limit(limit))).scalars())


async def author_affinity(s: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """How often the viewer liked each author recently (last 200 likes)."""
    recent = select(Like.post_id).where(Like.user_id == user_id).order_by(Like.created_at.desc()).limit(200).subquery()
    rows = await s.execute(select(Post.author_id).join(recent, recent.c.post_id == Post.id))
    counts: dict[uuid.UUID, int] = {}
    for author in rows.scalars():
        counts[author] = counts.get(author, 0) + 1
    return counts


async def liked_vectors(s: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> list[list[float]]:
    recent = select(Like.post_id).where(Like.user_id == user_id).order_by(Like.created_at.desc()).limit(limit).subquery()
    q = select(Embedding.vector).join(recent, Embedding.entity_id == recent.c.post_id.cast(Embedding.entity_id.type)).where(
        Embedding.entity_type == "post"
    )
    return [list(v) for v in (await s.execute(q)).scalars()]


async def post_vectors(s: AsyncSession, ids: list[uuid.UUID]) -> dict[str, list[float]]:
    if not ids:
        return {}
    q = select(Embedding.entity_id, Embedding.vector).where(
        Embedding.entity_type == "post", Embedding.entity_id.in_([str(i) for i in ids])
    )
    return {a: list(b) for a, b in (await s.execute(q)).all()}
