"""WebSocket gateway: chat events, notifications, presence, live counters."""
import asyncio
import uuid
from typing import Any

import jwt
import orjson
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.cache import get_redis
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.security import decode_token
from app.modules.chat import service as chat
from app.modules.posts import service as posts
from app.modules.users import repository as users
from app.realtime.pubsub import publish_user

router = APIRouter()
log = structlog.get_logger()
MAX_WATCHED = 50
PRESENCE_TTL = 60


def _origin_ok(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    if not origin:
        return False
    if origin in settings.origins or (settings.public_url and origin == settings.public_url):
        return True
    host = ws.headers.get("x-forwarded-host") or ws.headers.get("host") or ""
    return origin.split("://", 1)[-1] == host


@router.websocket("/ws")
async def gateway(ws: WebSocket) -> None:
    if not _origin_ok(ws):  # cross-site WebSocket hijacking defence
        await ws.close(code=4403)
        return
    try:
        payload = decode_token(ws.cookies.get("rsv_access", ""))
        user_id = uuid.UUID(str(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError):
        await ws.close(code=4401)
        return
    await ws.accept()

    client = get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(f"user:{user_id}")
    await client.set(f"presence:{user_id}", "1", ex=PRESENCE_TTL)
    watched: set[str] = set()

    async def pump() -> None:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            try:
                data: dict[str, Any] = orjson.loads(await ws.receive_text())
            except orjson.JSONDecodeError:
                continue
            await _handle(ws, user_id, data, pubsub, watched)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - one broken socket must not take down the worker
        log.warning("ws_error", error=str(exc))
    finally:
        pump_task.cancel()
        await pubsub.aclose()  # type: ignore[no-untyped-call]
        await client.delete(f"presence:{user_id}")


async def _handle(ws: WebSocket, user_id: uuid.UUID, data: dict[str, Any], pubsub: Any, watched: set[str]) -> None:
    kind = data.get("type")
    if kind == "ping":
        await get_redis().set(f"presence:{user_id}", "1", ex=PRESENCE_TTL)
        await ws.send_text('{"type":"pong"}')
    elif kind == "watch_post" and len(watched) < MAX_WATCHED:
        post_id = uuid.UUID(str(data["post_id"]))
        async with SessionLocal() as s:
            viewer = await users.by_id(s, user_id)
            try:
                await posts.get_viewable(s, viewer, post_id)  # counters only for posts you may see
            except AppError:
                return
        watched.add(str(post_id))
        await pubsub.subscribe(f"post:{post_id}")
    elif kind == "unwatch_post":
        post_id_s = str(data.get("post_id"))
        if post_id_s in watched:
            watched.discard(post_id_s)
            await pubsub.unsubscribe(f"post:{post_id_s}")
    elif kind in {"typing", "delivered"}:
        conversation_id = uuid.UUID(str(data["conversation_id"]))
        async with SessionLocal() as s:
            members = await chat.member_ids_if_member(s, user_id, conversation_id)
            if members is None:
                return
            if kind == "delivered":
                await chat.mark_delivered(s, user_id, conversation_id)
        for member in members:
            if member != user_id:
                await publish_user(member, {
                    "type": kind, "conversation_id": str(conversation_id), "user_id": str(user_id),
                })
