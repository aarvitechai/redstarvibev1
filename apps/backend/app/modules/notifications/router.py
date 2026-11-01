from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db
from app.core.pagination import Page, id_cursor
from app.modules.notifications import service
from app.modules.notifications.schemas import NotificationOut, PushPublicKey, PushSubscribe, UnreadCount

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=Page[NotificationOut])
async def list_all(
    me: CurrentUser, s: Db, cursor: str | None = None, limit: int = Query(30, ge=1, le=50)
) -> Page[NotificationOut]:
    return await service.list_page(s, me, id_cursor(cursor), limit)


@router.get("/notifications/unread-count", response_model=UnreadCount)
async def unread(me: CurrentUser, s: Db) -> UnreadCount:
    return await service.unread_count(s, me)


@router.post("/notifications/read", status_code=204)
async def read(me: CurrentUser, s: Db) -> None:
    await service.mark_read(s, me)


@router.get("/push/public-key", response_model=PushPublicKey)
async def public_key() -> PushPublicKey:
    return service.public_key()


@router.post("/push/subscribe", status_code=204)
async def subscribe(data: PushSubscribe, me: CurrentUser, s: Db) -> None:
    await service.subscribe(s, me, data)


@router.delete("/push/subscribe", status_code=204)
async def unsubscribe(data: PushSubscribe, me: CurrentUser, s: Db) -> None:
    await service.unsubscribe(s, me, data.endpoint)
