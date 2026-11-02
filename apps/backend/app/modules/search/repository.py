import uuid

from sqlalchemy import Text, cast, func, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.posts.models import Hashtag, Post, PostHashtag
from app.modules.posts.repository import visible_clause
from app.modules.users.models import Block, Profile, User

MAX_DISTANCE = 0.75  # cosine distance. Beyond this, a post is not about the query.


def _escape(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def users(s: AsyncSession, q: str, viewer: uuid.UUID | None, limit: int, offset: int) -> list[User]:
    """Trigram similarity, so typos still find the person."""
    username = cast(User.username, Text)
    like = f"%{_escape(q)}%"
    stmt = (
        select(User).join(Profile, Profile.user_id == User.id)
        .where(
            User.status == "active",
            or_(username.op("%")(q), Profile.display_name.op("%")(q), username.ilike(like, escape="\\"),
                Profile.display_name.ilike(like, escape="\\")),
        )
        .order_by(func.greatest(func.similarity(username, q), func.similarity(Profile.display_name, q)).desc(),
                  User.follower_count.desc(), User.id)
        .offset(offset).limit(limit)
    )
    if viewer:
        stmt = stmt.where(
            User.id.not_in(select(Block.blocker_id).where(Block.blocked_id == viewer)),
            User.id.not_in(select(Block.blocked_id).where(Block.blocker_id == viewer)),
        )
    return list((await s.execute(stmt)).scalars().unique())


async def hashtags(s: AsyncSession, q: str, limit: int, offset: int) -> list[Hashtag]:
    tag = cast(Hashtag.tag, Text)
    stmt = (
        select(Hashtag)
        .where(Hashtag.post_count > 0, or_(tag.op("%")(q), tag.ilike(f"{_escape(q)}%", escape="\\")))
        .order_by(func.similarity(tag, q).desc(), Hashtag.post_count.desc(), Hashtag.tag).offset(offset).limit(limit)
    )
    return list((await s.execute(stmt)).scalars())


async def places(s: AsyncSession, q: str, viewer: uuid.UUID | None, limit: int, offset: int) -> list[tuple[str, int]]:
    stmt = (
        select(Post.location, func.count()).join(User, User.id == Post.author_id)
        .where(Post.location.ilike(f"%{_escape(q)}%", escape="\\"), visible_clause(viewer))
        .group_by(Post.location).order_by(func.count().desc(), Post.location).offset(offset).limit(limit)
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


async def keyword_posts(s: AsyncSession, q: str, viewer: uuid.UUID | None, limit: int) -> list[uuid.UUID]:
    """Any word can match, and more matching words rank higher. The trigram match forgives typos."""
    query = func.cast(func.replace(func.cast(func.plainto_tsquery("simple", q), Text), "&", "|"), TSQUERY)
    closeness = func.word_similarity(q, Post.search_text)
    stmt = (
        select(Post.id).join(User, User.id == Post.author_id)
        .where(or_(Post.search_tsv.op("@@")(query), Post.search_text.op("%>")(q)), visible_clause(viewer))
        .order_by(func.ts_rank(Post.search_tsv, query).desc(), closeness.desc(), Post.id.desc()).limit(limit)
    )
    return list((await s.execute(stmt)).scalars())


async def semantic_posts(s: AsyncSession, vector: list[float], viewer: uuid.UUID | None, limit: int) -> list[uuid.UUID]:
    """The visibility filter runs in SQL, so private posts can never surface through search."""
    distance = Post.embedding.cosine_distance(vector)
    stmt = (
        select(Post.id).join(User, User.id == Post.author_id)
        .where(Post.embedding.is_not(None), distance < MAX_DISTANCE, visible_clause(viewer))
        .order_by(distance).limit(limit)
    )
    return list((await s.execute(stmt)).scalars())


async def embedding_of(s: AsyncSession, post_id: uuid.UUID) -> list[float] | None:
    value = (await s.execute(select(Post.embedding).where(Post.id == post_id))).scalar_one_or_none()
    return [float(x) for x in value] if value is not None else None


async def similar_posts(
    s: AsyncSession, post_id: uuid.UUID, vector: list[float], viewer: uuid.UUID | None, limit: int
) -> list[uuid.UUID]:
    distance = Post.embedding.cosine_distance(vector)
    stmt = (
        select(Post.id).join(User, User.id == Post.author_id)
        .where(Post.id != post_id, Post.embedding.is_not(None), distance < MAX_DISTANCE, visible_clause(viewer))
        .order_by(distance).limit(limit)
    )
    return list((await s.execute(stmt)).scalars())
