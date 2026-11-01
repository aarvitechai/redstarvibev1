"""Feed ranking v1: engagement, author affinity, taste similarity and freshness."""
import math
import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_many, cache_set_many
from app.modules.feed import repository as repo
from app.modules.posts.schemas import PostOut
from app.modules.users.models import User

SIGNALS_TTL = 300


def score_post(
    likes: int, comments: int, saves: int, age_hours: float, affinity: int, similarity: float
) -> float:
    engagement = math.log1p(likes + 2 * comments + 3 * saves)
    freshness = math.exp(-age_hours / 36)
    return 1.0 * engagement + 0.6 * math.log1p(affinity) + 1.5 * similarity + 3.0 * freshness


async def _signals(s: AsyncSession, user_id: uuid.UUID) -> tuple[dict[str, int], list[float] | None]:
    """Who the viewer likes and their taste vector. Slow to compute and slow to change, so cached."""
    key = f"rank:signals:{user_id}"
    cached = (await cache_get_many([key]))[0]
    if cached is not None:
        return cached["affinity"], cached["taste"]
    affinity = {str(k): v for k, v in (await repo.author_affinity(s, user_id)).items()}
    liked = await repo.liked_vectors(s, user_id)
    taste: list[float] | None = None
    if liked:
        mean = np.mean(np.asarray(liked), axis=0)
        taste = [float(x) for x in mean / (np.linalg.norm(mean) or 1.0)]
    await cache_set_many({key: {"affinity": affinity, "taste": taste}}, SIGNALS_TTL)
    return affinity, taste


async def rank_posts(s: AsyncSession, viewer: User | None, posts: list[PostOut]) -> list[PostOut]:
    """Reorders within the page only, so cursor pagination stays stable."""
    if len(posts) < 2:
        return posts
    affinity: dict[str, int] = {}
    taste = None
    vectors: dict[str, list[float]] = {}
    if viewer:
        affinity, taste_list = await _signals(s, viewer.id)
        if taste_list:
            taste = np.asarray(taste_list)
            vectors = await repo.post_vectors(s, [p.id for p in posts])
    now = datetime.now(UTC)

    def score(p: PostOut) -> float:
        age = max((now - p.created_at).total_seconds() / 3600, 0)
        similarity = 0.0
        vec = vectors.get(str(p.id))
        if taste is not None and vec is not None:
            similarity = float(np.dot(taste, np.asarray(vec)))
        return score_post(p.like_count, p.comment_count, p.save_count, age, affinity.get(str(p.author.id), 0), similarity)

    return sorted(posts, key=score, reverse=True)
