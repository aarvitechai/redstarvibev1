from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.provider import embed_query
from app.ai.vision.clip import embed_image_query
from app.core.config import settings
from app.core.pagination import Page, encode_cursor, id_cursor
from app.modules.posts import service as posts
from app.modules.posts.schemas import PostOut
from app.modules.search import repository as repo
from app.modules.search.schemas import HashtagOut, PlaceOut, SearchResults
from app.modules.users import service as user_service
from app.modules.users.models import User


async def search(s: AsyncSession, viewer: User | None, q: str, limit: int = 15) -> SearchResults:
    q = q.strip().lstrip("#@")
    if not q:
        return SearchResults()
    vid = viewer.id if viewer else None
    return SearchResults(
        users=[user_service.brief(u) for u in await repo.users(s, q, vid, limit)],
        hashtags=[HashtagOut(tag=h.tag, post_count=h.post_count) for h in await repo.hashtags(s, q, limit)],
        places=[PlaceOut(name=n, post_count=c) for n, c in await repo.places(s, q, vid, limit)],
    )


async def image_search(s: AsyncSession, viewer: User | None, q: str, limit: int = 24) -> list[PostOut]:
    """Natural language search. Uses CLIP when enabled, plus caption vectors and full text."""
    vid = viewer.id if viewer else None
    ranked: list = []  # type: ignore[type-arg]
    if settings.clip_enabled:
        clip = await embed_image_query(q)
        if clip:
            ranked.extend(await repo.vector_posts(s, clip, "post_image", vid, limit, 0.85))
    ranked.extend(await repo.text_posts(s, q, vid, limit))
    ranked.extend(await repo.vector_posts(s, await embed_query(q), "post", vid, limit, 0.8))
    ids = list(dict.fromkeys(ranked))[:limit]
    return await posts.hydrate(s, viewer, ids)


async def tag_page(s: AsyncSession, viewer: User | None, tag: str, cursor: str | None, limit: int) -> Page[PostOut]:
    ids = await repo.by_hashtag(s, tag, viewer.id if viewer else None, id_cursor(cursor), limit + 1)
    more = len(ids) > limit
    ids = ids[:limit]
    return Page(items=await posts.hydrate(s, viewer, ids), next_cursor=encode_cursor(ids[-1]) if more else None)


async def place_page(s: AsyncSession, viewer: User | None, place: str, cursor: str | None, limit: int) -> Page[PostOut]:
    ids = await repo.by_place(s, place, viewer.id if viewer else None, id_cursor(cursor), limit + 1)
    more = len(ids) > limit
    ids = ids[:limit]
    return Page(items=await posts.hydrate(s, viewer, ids), next_cursor=encode_cursor(ids[-1]) if more else None)
