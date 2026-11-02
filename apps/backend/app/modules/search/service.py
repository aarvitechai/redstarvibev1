"""Hybrid post search, people and tag search, and place and tag pages. AI is optional: keyword search always works."""
import hashlib
import json
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.search import embed_query
from app.core.cache import get_redis
from app.core.errors import bad_request
from app.core.pagination import Page, decode_cursor, encode_cursor, id_cursor
from app.core.rate_limit import hit
from app.modules.posts import service as posts
from app.modules.posts.schemas import PostOut
from app.modules.search import ranking
from app.modules.search import repository as repo
from app.modules.search.schemas import HashtagOut, PlaceOut, SearchSuggest
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.modules.users.schemas import UserBrief

MAX_QUERY = 100
CANDIDATES = 50  # taken from each of the keyword and vector lists
RESULT_CACHE_SECONDS = 60
MAX_OFFSET = 200


def normalize(q: str) -> str:
    return q.strip().lower().lstrip("#@").strip()[:MAX_QUERY]


def _offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, min(int(decode_cursor(cursor)[0]), MAX_OFFSET))
    except ValueError as exc:
        raise bad_request("invalid_cursor", "Invalid cursor") from exc


async def _rank(s: AsyncSession, viewer_id: uuid.UUID | None, q: str) -> list[uuid.UUID]:
    keyword = await repo.keyword_posts(s, q, viewer_id, CANDIDATES)
    vector = await embed_query(q)
    semantic = await repo.semantic_posts(s, vector, viewer_id, CANDIDATES) if vector else []
    return ranking.merge([keyword, semantic], int(time.time() * 1000))


async def _ranked_ids(s: AsyncSession, viewer: User | None, q: str) -> list[uuid.UUID]:
    """Only anonymous results are cached. They hold public posts alone, so the shared cache can never leak a private one."""
    if viewer:
        return await _rank(s, viewer.id, q)
    client = get_redis()
    key = f"search:res:{hashlib.sha256(q.encode()).hexdigest()}"
    cached = await client.get(key)
    if cached:
        return [uuid.UUID(i) for i in json.loads(cached)]
    ids = await _rank(s, None, q)
    await client.set(key, json.dumps([str(i) for i in ids]), ex=RESULT_CACHE_SECONDS)
    return ids


async def _limit(viewer: User | None) -> None:
    if viewer:
        await hit(f"search:user:{viewer.id}", 120, 60)


async def search_posts(s: AsyncSession, viewer: User | None, q: str, limit: int, offset: int = 0) -> list[PostOut]:
    q = normalize(q)
    if not q:
        return []
    ids = await _ranked_ids(s, viewer, q)
    return await posts.hydrate(s, viewer, ids[offset:offset + limit])


async def posts_page(s: AsyncSession, viewer: User | None, q: str, cursor: str | None, limit: int) -> Page[PostOut]:
    await _limit(viewer)
    offset = _offset(cursor)
    items = await search_posts(s, viewer, q, limit, offset)
    return Page(items=items, next_cursor=encode_cursor(offset + limit) if len(items) == limit else None)


async def users_page(s: AsyncSession, viewer: User | None, q: str, cursor: str | None, limit: int) -> Page[UserBrief]:
    await _limit(viewer)
    q, offset = normalize(q), _offset(cursor)
    rows = await repo.users(s, q, viewer.id if viewer else None, limit + 1, offset) if q else []
    more = len(rows) > limit
    return Page(
        items=[user_service.brief(u) for u in rows[:limit]], next_cursor=encode_cursor(offset + limit) if more else None
    )


async def tags_page(s: AsyncSession, viewer: User | None, q: str, cursor: str | None, limit: int) -> Page[HashtagOut]:
    await _limit(viewer)
    q, offset = normalize(q), _offset(cursor)
    rows = await repo.hashtags(s, q, limit + 1, offset) if q else []
    more = len(rows) > limit
    return Page(
        items=[HashtagOut(tag=h.tag, post_count=h.post_count) for h in rows[:limit]],
        next_cursor=encode_cursor(offset + limit) if more else None,
    )


async def places_page(s: AsyncSession, viewer: User | None, q: str, cursor: str | None, limit: int) -> Page[PlaceOut]:
    await _limit(viewer)
    q, offset = normalize(q), _offset(cursor)
    rows = await repo.places(s, q, viewer.id if viewer else None, limit + 1, offset) if q else []
    more = len(rows) > limit
    return Page(
        items=[PlaceOut(name=n, post_count=c) for n, c in rows[:limit]],
        next_cursor=encode_cursor(offset + limit) if more else None,
    )


async def suggest(s: AsyncSession, viewer: User | None, q: str) -> SearchSuggest:
    await _limit(viewer)
    q = normalize(q)
    if not q:
        return SearchSuggest(users=[], tags=[])
    return SearchSuggest(
        users=[user_service.brief(u) for u in await repo.users(s, q, viewer.id if viewer else None, 5, 0)],
        tags=[HashtagOut(tag=h.tag, post_count=h.post_count) for h in await repo.hashtags(s, q, 5, 0)],
    )


async def similar_posts(s: AsyncSession, viewer: User | None, post_id: uuid.UUID, limit: int) -> list[PostOut]:
    await posts.get_viewable(s, viewer, post_id)
    vector = await repo.embedding_of(s, post_id)
    if vector is None:
        return []
    return await posts.hydrate(s, viewer, await repo.similar_posts(s, post_id, vector, viewer.id if viewer else None, limit))


async def tag_page(s: AsyncSession, viewer: User | None, tag: str, cursor: str | None, limit: int) -> Page[PostOut]:
    ids = await repo.by_hashtag(s, tag, viewer.id if viewer else None, id_cursor(cursor), limit + 1)
    more = len(ids) > limit
    ids = ids[:limit]
    return Page(items=await posts.hydrate(s, viewer, ids), next_cursor=encode_cursor(ids[-1]) if more else None)


async def tag_top_page(s: AsyncSession, viewer: User | None, tag: str, cursor: str | None, limit: int) -> Page[PostOut]:
    after: tuple[int, uuid.UUID] | None = None
    if cursor:
        try:
            score, post_id = decode_cursor(cursor)
            after = (int(score), uuid.UUID(post_id))
        except ValueError as exc:
            raise bad_request("invalid_cursor", "Invalid cursor") from exc
    rows = await repo.top_by_hashtag(s, tag, viewer.id if viewer else None, after, limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    items = await posts.hydrate(s, viewer, [r[0] for r in rows])
    return Page(items=items, next_cursor=encode_cursor(rows[-1][1], rows[-1][0]) if more else None)


async def place_page(s: AsyncSession, viewer: User | None, place: str, cursor: str | None, limit: int) -> Page[PostOut]:
    ids = await repo.by_place(s, place, viewer.id if viewer else None, id_cursor(cursor), limit + 1)
    more = len(ids) > limit
    ids = ids[:limit]
    return Page(items=await posts.hydrate(s, viewer, ids), next_cursor=encode_cursor(ids[-1]) if more else None)
