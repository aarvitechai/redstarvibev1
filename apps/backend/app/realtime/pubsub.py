"""Any pod can publish. Each gateway pod subscribes only to channels of its connected users."""
import uuid
from typing import Any

import orjson

from app.core.cache import get_redis


async def publish(channel: str, payload: dict[str, Any]) -> None:
    await get_redis().publish(channel, orjson.dumps(payload, default=str).decode())


async def publish_user(user_id: uuid.UUID | str, payload: dict[str, Any]) -> None:
    await publish(f"user:{user_id}", payload)


async def is_online(user_id: uuid.UUID | str) -> bool:
    return bool(await get_redis().exists(f"presence:{user_id}"))
