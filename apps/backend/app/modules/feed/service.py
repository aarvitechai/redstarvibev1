"""Home feed: precomputed in Redis (fan-out on write), celebrities merged on read, then ranked."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ranking.ranker import rank_posts
from app.core.cache import get_redis
from app.core.config import settings
from app.core.pagination import Page, decode_cursor, encode_cursor, id_cursor
from app.modules.feed import repository as repo
from app.modules.posts import service as posts
from app.modules.posts.schemas import PostOut
from app.modules.users import repository as users
from app.modules.users.models import User

SENTINEL = "0"  # marks a built but empty feed, so fan-out knows the key is authoritative


def feed_key(user_id: uuid.UUID) -> str:
    return f"feed:{user_id}"


def post_score(post_id: uuid.UUID) -> int:
    return int(post_id.hex[:12], 16)  # UUIDv7 timestamp in milliseconds


async def _ensure_built(s: AsyncSession, user_id: uuid.UUID) -> None:
    client = get_redis()
    key = feed_key(user_id)
    if await client.exists(key):
        return
    ids = await repo.recent_for_rebuild(s, user_id, settings.feed_max_items)
    mapping: dict[str, int] = {SENTINEL: 0}
    mapping.update({str(i): post_score(i) for i in ids})
    pipe = client.pipeline()
    pipe.zadd(key, mapping)
    pipe.expire(key, settings.feed_ttl_seconds)
    await pipe.execute()


async def home_feed(s: AsyncSession, user: User, cursor: str | None, limit: int) -> Page[PostOut]:
    await _ensure_built(s, user.id)
    client = get_redis()
    max_score: str | int = "+inf"
    before: uuid.UUID | None = None
    if cursor:
        before = uuid.UUID(decode_cursor(cursor)[0])
        max_score = f"({post_score(before)}"
    raw = await client.zrevrangebyscore(feed_key(user.id), max_score, "(0", start=0, num=limit + 1)
    ids = [uuid.UUID(str(r)) for r in raw]
    ids += await repo.celebrity_post_ids(s, user.id, settings.celebrity_threshold, before, limit + 1)
    ids = sorted(set(ids), key=post_score, reverse=True)
    more = len(ids) > limit
    ids = ids[:limit]

    blocked = await users.blocked_ids(s, user.id) | await users.limit_ids(s, user.id, "mute")
    items = [
        p for p in await posts.hydrate(s, user, ids)
        if p.status == "published" and p.author.id not in blocked
    ]
    ranked = await rank_posts(s, user, items)
    return Page(items=ranked, next_cursor=encode_cursor(ids[-1]) if more and ids else None)


async def explore(s: AsyncSession, viewer: User | None, cursor: str | None, limit: int) -> Page[PostOut]:
    ids = await repo.explore_ids(s, viewer.id if viewer else None, id_cursor(cursor), limit + 1)
    more = len(ids) > limit
    ids = ids[:limit]
    items = await posts.hydrate(s, viewer, ids)
    ranked = await rank_posts(s, viewer, items)
    return Page(items=ranked, next_cursor=encode_cursor(ids[-1]) if more else None)


async def fan_out(post_id: uuid.UUID, follower_ids: list[uuid.UUID]) -> None:
    """Only touch feeds that are already built. Others rebuild from Postgres on next read."""
    client = get_redis()
    score = post_score(post_id)
    for start in range(0, len(follower_ids), 500):
        batch = follower_ids[start:start + 500]
        check = client.pipeline(transaction=False)
        for uid in batch:
            check.exists(feed_key(uid))
        exists = await check.execute()
        pipe = client.pipeline(transaction=False)
        for uid, present in zip(batch, exists, strict=True):
            if present:
                key = feed_key(uid)
                pipe.zadd(key, {str(post_id): score})
                pipe.zremrangebyrank(key, 0, -(settings.feed_max_items + 2))
                pipe.expire(key, settings.feed_ttl_seconds)
        await pipe.execute()


async def remove_from_feeds(post_id: uuid.UUID, follower_ids: list[uuid.UUID]) -> None:
    pipe = get_redis().pipeline(transaction=False)
    for uid in follower_ids:
        pipe.zrem(feed_key(uid), str(post_id))
    await pipe.execute()


async def invalidate_feed(user_id: uuid.UUID) -> None:
    await get_redis().delete(feed_key(user_id))
