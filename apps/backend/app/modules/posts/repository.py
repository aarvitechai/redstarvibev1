import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.comments.models import Comment
from app.modules.follows.models import Follow
from app.modules.posts.models import Collection, Hashtag, Like, Post, PostCollab, PostHashtag, PostMedia, PostTag, Save
from app.modules.users.models import Block, User


def visible_clause(viewer_id: uuid.UUID | None) -> ColumnElement[bool]:
    """Object level visibility in SQL. Keep in sync with service.can_view."""
    base = and_(Post.status == "published", Post.deleted_at.is_(None), User.status == "active")
    public = and_(Post.visibility == "public", User.is_private.is_(False))
    if viewer_id is None:
        return and_(base, public)
    # Aliases: callers may already join these tables, which would otherwise auto-correlate away.
    f, b = aliased(Follow), aliased(Block)
    follows = exists().where(f.follower_id == viewer_id, f.followee_id == Post.author_id, f.status == "active")
    blocked = exists().where(or_(
        and_(b.blocker_id == viewer_id, b.blocked_id == Post.author_id),
        and_(b.blocker_id == Post.author_id, b.blocked_id == viewer_id),
    ))
    return and_(base, ~blocked, or_(public, Post.author_id == viewer_id, follows))


async def pending_collab_post_ids(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    q = (
        select(Post.id).join(PostCollab, PostCollab.post_id == Post.id)
        .where(
            PostCollab.user_id == user_id, PostCollab.status == "pending", Post.status == "published",
            Post.deleted_at.is_(None),
        )
    )
    return list((await s.execute(q.order_by(Post.id.desc()).limit(50))).scalars())


async def set_collab_accepted(s: AsyncSession, post_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    stmt = (
        update(PostCollab).where(PostCollab.post_id == post_id, PostCollab.user_id == user_id, PostCollab.status == "pending")
        .values(status="accepted").returning(PostCollab.post_id)
    )
    return (await s.execute(stmt)).first() is not None


async def remove_collab(s: AsyncSession, post_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    stmt = delete(PostCollab).where(PostCollab.post_id == post_id, PostCollab.user_id == user_id).returning(PostCollab.post_id)
    return (await s.execute(stmt)).first() is not None


def _live_pins(author: uuid.UUID) -> ColumnElement[bool]:
    return and_(Post.author_id == author, Post.pinned_at.is_not(None), Post.status == "published", Post.deleted_at.is_(None))


async def pinned_count(s: AsyncSession, author: uuid.UUID) -> int:
    return int((await s.execute(select(func.count()).select_from(Post).where(_live_pins(author)))).scalar_one())


async def pinned_post_ids(s: AsyncSession, author: uuid.UUID, include_followers: bool) -> list[uuid.UUID]:
    q = select(Post.id).where(_live_pins(author))
    if not include_followers:
        q = q.where(Post.visibility == "public")
    return list((await s.execute(q.order_by(Post.pinned_at.desc()))).scalars())


async def capsule_summary(s: AsyncSession, author: uuid.UUID) -> tuple[int, datetime | None]:
    q = select(func.count(), func.min(Post.scheduled_at)).where(
        Post.author_id == author, Post.is_capsule.is_(True), Post.status == "scheduled", Post.deleted_at.is_(None)
    )
    row = (await s.execute(q)).one()
    return int(row[0]), row[1]


async def remove_tag(s: AsyncSession, post_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    stmt = delete(PostTag).where(PostTag.post_id == post_id, PostTag.user_id == user_id).returning(PostTag.user_id)
    res = await s.execute(stmt)
    return res.first() is not None


async def tagged_post_ids(
    s: AsyncSession, user_id: uuid.UUID, viewer: uuid.UUID | None, cursor: uuid.UUID | None, limit: int
) -> list[uuid.UUID]:
    q = (
        select(Post.id).join(User, User.id == Post.author_id).join(PostTag, PostTag.post_id == Post.id)
        .where(PostTag.user_id == user_id, visible_clause(viewer))
    )
    if cursor:
        q = q.where(Post.id < cursor)
    return list((await s.execute(q.order_by(Post.id.desc()).limit(limit))).scalars())


async def add(s: AsyncSession, post: Post) -> None:
    s.add(post)
    await s.flush()


async def get(s: AsyncSession, post_id: uuid.UUID) -> Post | None:
    q = select(Post).where(Post.id == post_id, Post.deleted_at.is_(None)).execution_options(populate_existing=True)
    return (await s.execute(q)).scalars().first()


async def get_many(s: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Post]:
    if not ids:
        return []
    return list((await s.execute(select(Post).where(Post.id.in_(ids)))).scalars().unique())


async def author_post_ids(
    s: AsyncSession, author: uuid.UUID, include_followers: bool, cursor: uuid.UUID | None, limit: int, reels: bool
) -> list[uuid.UUID]:
    collabs = select(PostCollab.post_id).where(PostCollab.user_id == author, PostCollab.status == "accepted")
    q = select(Post.id).where(
        or_(Post.author_id == author, Post.id.in_(collabs)), Post.status == "published", Post.deleted_at.is_(None)
    )
    if not include_followers:
        q = q.where(Post.visibility == "public")
    if reels:
        q = q.where(Post.is_reel.is_(True))
    else:  # pinned posts lead the first page, so they must not repeat further down
        q = q.where(or_(Post.author_id != author, Post.pinned_at.is_(None)))
    if cursor:
        q = q.where(Post.id < cursor)
    return list((await s.execute(q.order_by(Post.id.desc()).limit(limit))).scalars())


async def like(s: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> bool:
    res = await s.execute(
        insert(Like).values(user_id=user_id, post_id=post_id).on_conflict_do_nothing().returning(Like.post_id)
    )
    return res.first() is not None


async def unlike(s: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> bool:
    res = await s.execute(delete(Like).where(Like.user_id == user_id, Like.post_id == post_id).returning(Like.post_id))
    return res.first() is not None


async def liked_among(s: AsyncSession, user_id: uuid.UUID, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    q = select(Like.post_id).where(Like.user_id == user_id, Like.post_id.in_(ids))
    return set((await s.execute(q)).scalars())


async def saved_among(s: AsyncSession, user_id: uuid.UUID, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    q = select(Save.post_id).where(Save.user_id == user_id, Save.post_id.in_(ids))
    return set((await s.execute(q)).scalars())


async def save(s: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID, collection_id: uuid.UUID | None) -> bool:
    stmt = insert(Save).values(user_id=user_id, post_id=post_id, collection_id=collection_id)
    existing = await s.get(Save, (user_id, post_id))
    await s.execute(stmt.on_conflict_do_update(index_elements=["user_id", "post_id"], set_={"collection_id": collection_id}))
    return existing is None


async def unsave(s: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> bool:
    res = await s.execute(delete(Save).where(Save.user_id == user_id, Save.post_id == post_id).returning(Save.post_id))
    return res.first() is not None


async def saved_ids(
    s: AsyncSession, viewer: uuid.UUID, collection_id: uuid.UUID | None, cursor: uuid.UUID | None, limit: int
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    q = (
        select(Save.id, Save.post_id).join(Post, Post.id == Save.post_id).join(User, User.id == Post.author_id)
        .where(Save.user_id == viewer, visible_clause(viewer))
    )
    if collection_id:
        q = q.where(Save.collection_id == collection_id)
    if cursor:
        q = q.where(Save.id < cursor)
    return [(a, b) for a, b in (await s.execute(q.order_by(Save.id.desc()).limit(limit))).all()]


async def add_collection(s: AsyncSession, collection: Collection) -> None:
    s.add(collection)
    await s.flush()


async def collections(s: AsyncSession, user_id: uuid.UUID) -> list[Collection]:
    q = select(Collection).where(Collection.user_id == user_id).order_by(Collection.id.desc())
    return list((await s.execute(q)).scalars())


async def collection(s: AsyncSession, collection_id: uuid.UUID) -> Collection | None:
    return await s.get(Collection, collection_id)


async def remove_collection(s: AsyncSession, collection_id: uuid.UUID) -> None:
    await s.execute(delete(Collection).where(Collection.id == collection_id))


async def own_posts_by_status(s: AsyncSession, user_id: uuid.UUID, statuses: Sequence[str]) -> list[uuid.UUID]:
    q = select(Post.id).where(Post.author_id == user_id, Post.status.in_(statuses), Post.deleted_at.is_(None))
    return list((await s.execute(q.order_by(Post.id.desc()).limit(100))).scalars())


async def link_hashtags(s: AsyncSession, post_id: uuid.UUID, tags: Sequence[str]) -> None:
    for tag in tags:
        await s.execute(
            insert(Hashtag).values(tag=tag, post_count=1)
            .on_conflict_do_update(index_elements=["tag"], set_={"post_count": Hashtag.post_count + 1})
        )
        await s.execute(insert(PostHashtag).values(tag=tag, post_id=post_id).on_conflict_do_nothing())


async def unlink_hashtags(s: AsyncSession, post_id: uuid.UUID) -> None:
    res = await s.execute(delete(PostHashtag).where(PostHashtag.post_id == post_id).returning(PostHashtag.tag))
    tags = list(res.scalars())
    if tags:
        await s.execute(update(Hashtag).where(Hashtag.tag.in_(tags)).values(post_count=Hashtag.post_count - 1))


async def apply_counters(s: AsyncSession, post_id: uuid.UUID, deltas: dict[str, int]) -> None:
    allowed = {k: v for k, v in deltas.items() if k in {"like_count", "comment_count", "view_count", "save_count"}}
    if not allowed:
        return
    values = {k: func.greatest(getattr(Post, k) + v, 0) for k, v in allowed.items()}
    await s.execute(update(Post).where(Post.id == post_id).values(**values))
    await s.execute(
        update(Post).where(Post.id == post_id).values(
            engagement_score=Post.like_count + 2 * Post.comment_count + 3 * Post.save_count + 0.05 * Post.view_count
        )
    )


async def due_scheduled(s: AsyncSession, limit: int = 100) -> list[uuid.UUID]:
    q = select(Post.id).where(
        Post.status == "scheduled", Post.scheduled_at <= datetime.now(UTC), Post.deleted_at.is_(None)
    ).limit(limit)
    return list((await s.execute(q)).scalars())


async def export_comments(s: AsyncSession, user_id: uuid.UUID) -> list[Comment]:
    q = select(Comment).where(Comment.author_id == user_id, Comment.deleted_at.is_(None)).limit(10000)
    return list((await s.execute(q)).scalars().unique())


async def export_posts(s: AsyncSession, user_id: uuid.UUID) -> list[Post]:
    q = select(Post).where(Post.author_id == user_id, Post.deleted_at.is_(None)).limit(10000)
    return list((await s.execute(q)).scalars().unique())


async def export_saved(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list((await s.execute(select(Save.post_id).where(Save.user_id == user_id))).scalars())


__all__ = ["PostMedia", "visible_clause"]
