import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.events import enqueue
from app.core.pagination import Page, encode_cursor
from app.modules.notifications import repository as repo
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationOut, PushPublicKey, PushSubscribe, UnreadCount
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.realtime.pubsub import is_online, publish_user

PUSH_TEXT = {
    "like": "{actor} liked your post",
    "comment": "{actor} commented on your post",
    "mention": "{actor} mentioned you",
    "follow": "{actor} started following you",
    "follow_request": "{actor} asked to follow you",
    "follow_accepted": "{actor} accepted your follow request",
    "new_post": "{actor} shared a new post",
    "message": "{actor} sent you a message",
    "live": "{actor} is live now",
    "post_failed": "Your post could not be published",
    "post_published": "Your post is live",
}


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id, type=n.type, actor=user_service.brief(n.actor) if n.actor else None, entity_id=n.entity_id,
        read=n.read_at is not None, created_at=n.created_at,
    )


async def notify(
    s: AsyncSession, user_id: uuid.UUID, kind: str, actor_id: uuid.UUID | None = None, entity_id: uuid.UUID | None = None
) -> None:
    if actor_id == user_id:
        return
    if actor_id and await users.is_blocked_either_way(s, user_id, actor_id):
        return
    n = Notification(user_id=user_id, type=kind, actor_id=actor_id, entity_id=entity_id)
    await repo.add(s, n)
    await s.commit()
    actor = await users.by_id(s, actor_id) if actor_id else None
    n.actor = actor
    await publish_user(user_id, {"type": "notification", "notification": _out(n).model_dump(mode="json")})
    if not await is_online(user_id):
        text = PUSH_TEXT.get(kind, "New activity on RedStarVibe").format(actor=actor.username if actor else "Someone")
        await enqueue("notifications.web_push", user_id, text, _url_for(kind, actor, entity_id))


def _url_for(kind: str, actor: User | None, entity_id: uuid.UUID | None) -> str:
    if kind in {"like", "comment", "mention", "new_post", "post_published"} and entity_id:
        return f"/p/{entity_id}"
    if kind == "message" and entity_id:
        return f"/messages/{entity_id}"
    if actor:
        return f"/{actor.username}"
    return "/notifications"


async def list_page(s: AsyncSession, me: User, cursor: uuid.UUID | None, limit: int) -> Page[NotificationOut]:
    rows = await repo.page(s, me.id, cursor, limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(items=[_out(n) for n in rows], next_cursor=encode_cursor(rows[-1].id) if more else None)


async def unread_count(s: AsyncSession, me: User) -> UnreadCount:
    return UnreadCount(count=await repo.unread(s, me.id))


async def mark_read(s: AsyncSession, me: User) -> None:
    await repo.mark_all_read(s, me.id)
    await s.commit()


async def subscribe(s: AsyncSession, me: User, data: PushSubscribe) -> None:
    await repo.upsert_push(s, me.id, data.endpoint, data.keys.p256dh, data.keys.auth)
    await s.commit()


async def unsubscribe(s: AsyncSession, me: User, endpoint: str) -> None:
    await repo.delete_push(s, me.id, endpoint)
    await s.commit()


def public_key() -> PushPublicKey:
    return PushPublicKey(public_key=settings.vapid_public_key or None)
