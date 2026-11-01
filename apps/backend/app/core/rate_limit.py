"""Sliding window rate limits in Redis, per user and per IP."""
import time
import uuid

from fastapi import Request

from app.core.cache import get_redis
from app.core.errors import AppError


def client_ip(request: Request) -> str:
    # nginx overwrites X-Real-IP, so a client cannot spoof it when behind the gateway.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


async def hit(bucket: str, limit: int, window_seconds: int) -> None:
    key = f"rl:{bucket}"
    now = time.time()
    pipe = get_redis().pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)
    pipe.zadd(key, {uuid.uuid4().hex: now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds)
    _, _, count, _ = await pipe.execute()
    if count > limit:
        raise AppError(429, "rate_limited", "Too many requests. Please slow down and try again shortly.")


async def check(bucket: str, limit: int, window_seconds: int) -> None:
    """Rejects if the bucket is already full, without counting this request."""
    key = f"rl:{bucket}"
    pipe = get_redis().pipeline()
    pipe.zremrangebyscore(key, 0, time.time() - window_seconds)
    pipe.zcard(key)
    _, count = await pipe.execute()
    if count >= limit:
        raise AppError(429, "rate_limited", "Too many attempts. Please wait a few minutes and try again.")


def ip_limit(name: str, limit: int, window_seconds: int):  # type: ignore[no-untyped-def]
    async def dep(request: Request) -> None:
        await hit(f"{name}:ip:{client_ip(request)}", limit, window_seconds)

    return dep
