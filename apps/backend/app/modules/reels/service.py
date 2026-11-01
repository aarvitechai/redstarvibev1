from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, encode_cursor, id_cursor
from app.modules.feed import repository as feed_repo
from app.modules.posts import service as posts
from app.modules.posts.schemas import PostOut
from app.modules.users.models import User


async def reels_page(s: AsyncSession, viewer: User | None, cursor: str | None, limit: int) -> Page[PostOut]:
    ids = await feed_repo.explore_ids(s, viewer.id if viewer else None, id_cursor(cursor), limit + 1, reels_only=True)
    more = len(ids) > limit
    ids = ids[:limit]
    return Page(items=await posts.hydrate(s, viewer, ids), next_cursor=encode_cursor(ids[-1]) if more else None)
