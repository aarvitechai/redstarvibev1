import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.follows.models import Follow
from app.modules.posts.models import Like, Post, PostCollab, PostHashtag
from app.modules.posts.repository import visible_clause
from app.modules.users.models import User

FOR_YOU_MAX_DISTANCE = 0.75  # cosine distance. Beyond this, a post has little to do with the person's taste.


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
    q = select(Post.embedding).join(recent, Post.id == recent.c.post_id).where(Post.embedding.is_not(None))
    return [[float(x) for x in v] for v in (await s.execute(q)).scalars()]


async def post_vectors(s: AsyncSession, ids: list[uuid.UUID]) -> dict[str, list[float]]:
    if not ids:
        return {}
    q = select(Post.id, Post.embedding).where(Post.id.in_(ids), Post.embedding.is_not(None))
    return {str(a): [float(x) for x in b] for a, b in (await s.execute(q)).all()}


async def liked_tags(s: AsyncSession, user_id: uuid.UUID, limit: int = 10) -> list[str]:
    recent = select(Like.post_id).where(Like.user_id == user_id).order_by(Like.created_at.desc()).limit(200).subquery()
    q = (
        select(PostHashtag.tag).join(recent, PostHashtag.post_id == recent.c.post_id)
        .group_by(PostHashtag.tag).order_by(func.count().desc()).limit(limit)
    )
    return [str(t) for t in (await s.execute(q)).scalars()]


def _for_you_base(viewer: uuid.UUID, hidden: set[uuid.UUID]):  # type: ignore[no-untyped-def]
    """Public posts from people the viewer does not follow, not yet liked, and never from anyone they muted."""
    followed = select(Follow.followee_id).where(Follow.follower_id == viewer)
    liked = select(Like.post_id).where(Like.user_id == viewer)
    q = (
        select(Post.id).join(User, User.id == Post.author_id)
        .where(
            visible_clause(viewer), Post.visibility == "public", User.is_private.is_(False), Post.author_id != viewer,
            Post.author_id.not_in(followed), Post.id.not_in(liked),
        )
    )
    return q.where(Post.author_id.not_in(hidden)) if hidden else q


async def for_you_nearest(
    s: AsyncSession, viewer: uuid.UUID, taste: list[float], hidden: set[uuid.UUID], limit: int
) -> list[uuid.UUID]:
    distance = Post.embedding.cosine_distance(taste)
    q = _for_you_base(viewer, hidden).where(Post.embedding.is_not(None), distance < FOR_YOU_MAX_DISTANCE).order_by(distance)
    return list((await s.execute(q.limit(limit))).scalars())


async def for_you_tagged(
    s: AsyncSession, viewer: uuid.UUID, tags: list[str], hidden: set[uuid.UUID], limit: int
) -> list[uuid.UUID]:
    tagged = select(PostHashtag.post_id).where(PostHashtag.tag.in_(tags))
    q = _for_you_base(viewer, hidden).where(Post.id.in_(tagged)).order_by(Post.engagement_score.desc(), Post.id.desc())
    return list((await s.execute(q.limit(limit))).scalars())
