import uuid

from sqlalchemy import func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import Embedding
from app.modules.posts.models import Hashtag, Post, PostHashtag
from app.modules.posts.repository import visible_clause
from app.modules.users.models import Block, Profile, User


def _escape(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def users(s: AsyncSession, q: str, viewer: uuid.UUID | None, limit: int) -> list[User]:
    like = f"%{_escape(q)}%"
    stmt = (
        select(User).join(Profile, Profile.user_id == User.id)
        .where(
            User.status == "active",
            (User.username.ilike(like, escape="\\")) | (Profile.display_name.ilike(like, escape="\\")),
        )
        .order_by(User.follower_count.desc()).limit(limit)
    )
    if viewer:
        stmt = stmt.where(User.id.not_in(select(Block.blocker_id).where(Block.blocked_id == viewer)))
    return list((await s.execute(stmt)).scalars().unique())


async def hashtags(s: AsyncSession, q: str, limit: int) -> list[Hashtag]:
    stmt = (
        select(Hashtag).where(Hashtag.tag.ilike(f"{_escape(q)}%", escape="\\"), Hashtag.post_count > 0)
        .order_by(Hashtag.post_count.desc()).limit(limit)
    )
    return list((await s.execute(stmt)).scalars())


async def places(s: AsyncSession, q: str, viewer: uuid.UUID | None, limit: int) -> list[tuple[str, int]]:
    stmt = (
        select(Post.location, func.count()).join(User, User.id == Post.author_id)
        .where(Post.location.ilike(f"%{_escape(q)}%", escape="\\"), visible_clause(viewer))
        .group_by(Post.location).order_by(func.count().desc()).limit(limit)
    )
    return [(str(a), int(b)) for a, b in (await s.execute(stmt)).all()]


async def by_hashtag(
    s: AsyncSession, tag: str, viewer: uuid.UUID | None, cursor: uuid.UUID | None, limit: int
) -> list[uuid.UUID]:
    stmt = (
        select(Post.id).join(User, User.id == Post.author_id).join(PostHashtag, PostHashtag.post_id == Post.id)
        .where(PostHashtag.tag == tag, visible_clause(viewer))
    )
    if cursor:
        stmt = stmt.where(Post.id < cursor)
    return list((await s.execute(stmt.order_by(Post.id.desc()).limit(limit))).scalars())


async def top_by_hashtag(
    s: AsyncSession, tag: str, viewer: uuid.UUID | None, after: tuple[int, uuid.UUID] | None, limit: int
) -> list[tuple[uuid.UUID, int]]:
    score = Post.like_count + Post.comment_count * 2 + Post.save_count * 3
    stmt = (
        select(Post.id, score).join(User, User.id == Post.author_id).join(PostHashtag, PostHashtag.post_id == Post.id)
        .where(PostHashtag.tag == tag, visible_clause(viewer))
    )
    if after:
        stmt = stmt.where(tuple_(score, Post.id) < tuple_(literal(after[0]), literal(after[1])))
    rows = await s.execute(stmt.order_by(score.desc(), Post.id.desc()).limit(limit))
    return [(r[0], r[1]) for r in rows]


async def by_place(
    s: AsyncSession, place: str, viewer: uuid.UUID | None, cursor: uuid.UUID | None, limit: int
) -> list[uuid.UUID]:
    stmt = select(Post.id).join(User, User.id == Post.author_id).where(Post.location == place, visible_clause(viewer))
    if cursor:
        stmt = stmt.where(Post.id < cursor)
    return list((await s.execute(stmt.order_by(Post.id.desc()).limit(limit))).scalars())


async def vector_posts(
    s: AsyncSession, vector: list[float], entity_type: str, viewer: uuid.UUID | None, limit: int, max_distance: float
) -> list[uuid.UUID]:
    """The visibility filter runs in SQL, so private posts can never surface through search."""
    distance = Embedding.vector.cosine_distance(vector)
    stmt = (
        select(Post.id).join(User, User.id == Post.author_id)
        .join(Embedding, Embedding.entity_id == func.cast(Post.id, Embedding.entity_id.type))
        .where(Embedding.entity_type == entity_type, visible_clause(viewer), distance < max_distance)
        .order_by(distance).limit(limit)
    )
    return list((await s.execute(stmt)).scalars())


async def text_posts(s: AsyncSession, q: str, viewer: uuid.UUID | None, limit: int) -> list[uuid.UUID]:
    query = func.plainto_tsquery("simple", q)
    vector = func.to_tsvector("simple", Post.caption)
    stmt = (
        select(Post.id).join(User, User.id == Post.author_id)
        .where(vector.op("@@")(query), visible_clause(viewer))
        .order_by(func.ts_rank(vector, query).desc()).limit(limit)
    )
    return list((await s.execute(stmt)).scalars())
