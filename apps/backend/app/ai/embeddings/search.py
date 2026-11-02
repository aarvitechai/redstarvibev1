"""Embeddings for post search. A query waits only briefly, so a slow API can never slow search down."""
import hashlib
import json

from app.ai import workers_ai
from app.core.cache import get_redis
from app.core.config import settings

QUERY_TIMEOUT = 3.0
INDEX_TIMEOUT = 300.0
QUERY_CACHE_SECONDS = 86400


def is_enabled() -> bool:
    return settings.cloudflare_ready and bool(settings.embed_model)


async def embed_many(texts: list[str]) -> list[list[float]] | None:
    if not is_enabled():
        return None
    return await workers_ai.embed(settings.embed_model, texts, INDEX_TIMEOUT)


async def embed_query(normalized: str) -> list[float] | None:
    if not is_enabled():
        return None
    digest = hashlib.sha256(f"{settings.embed_model}:{normalized}".encode()).hexdigest()
    key = f"search:q:{digest}"
    client = get_redis()
    cached = await client.get(key)
    if cached:
        vector: list[float] = json.loads(cached)
        return vector
    vectors = await workers_ai.embed(settings.embed_model, [normalized], QUERY_TIMEOUT)
    if not vectors:
        return None
    await client.set(key, json.dumps(vectors[0]), ex=QUERY_CACHE_SECONDS)
    return vectors[0]
