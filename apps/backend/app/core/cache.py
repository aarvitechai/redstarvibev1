"""Redis client (one per event loop), JSON cache aside helpers and the counter buffer."""
import asyncio
import uuid
from typing import Any

import orjson
import redis.asyncio as aioredis

from app.core.config import settings

_clients: dict[int, aioredis.Redis] = {}


def get_redis() -> aioredis.Redis:
    key = id(asyncio.get_running_loop())
    client = _clients.get(key)
    if client is None:
        client = aioredis.from_url(settings.redis_url, decode_responses=True, health_check_interval=30)
        _clients[key] = client
    return client


async def cache_get_many(keys: list[str]) -> list[Any | None]:
    if not keys:
        return []
    raw = await get_redis().mget(keys)
    return [orjson.loads(v) if v else None for v in raw]


async def cache_set_many(items: dict[str, Any], ttl: int) -> None:
    if not items:
        return
    pipe = get_redis().pipeline(transaction=False)
    for key, value in items.items():
        pipe.set(key, orjson.dumps(value, default=str).decode(), ex=ttl)
    await pipe.execute()


async def cache_delete(*keys: str) -> None:
    if keys:
        await get_redis().delete(*keys)


# ---- counters: Redis INCR, flushed to Postgres every few seconds ----
DIRTY = "counters:dirty"


async def counter_incr(post_id: uuid.UUID, field: str, delta: int = 1) -> None:
    key = f"counters:post:{post_id}"
    pipe = get_redis().pipeline()
    pipe.hincrby(key, field, delta)
    pipe.sadd(DIRTY, str(post_id))
    await pipe.execute()


async def counter_pending(post_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    if not post_ids:
        return {}
    pipe = get_redis().pipeline(transaction=False)
    for pid in post_ids:
        pipe.hgetall(f"counters:post:{pid}")
    rows = await pipe.execute()
    return {pid: {k: int(v) for k, v in row.items()} for pid, row in zip(post_ids, rows, strict=True) if row}


async def counter_drain(batch: int = 1000) -> dict[uuid.UUID, dict[str, int]]:
    client = get_redis()
    ids = await client.spop(DIRTY, batch)
    result: dict[uuid.UUID, dict[str, int]] = {}
    for raw_id in ids or []:
        pid = str(raw_id)
        key = f"counters:post:{pid}"
        pipe = client.pipeline(transaction=True)
        pipe.hgetall(key)
        pipe.delete(key)
        row, _ = await pipe.execute()
        if row:
            result[uuid.UUID(pid)] = {k: int(v) for k, v in row.items()}
    return result
