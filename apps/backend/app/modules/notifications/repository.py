import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification, PushSubscription


async def add(s: AsyncSession, n: Notification) -> None:
    n.created_at = datetime.now(UTC)
    s.add(n)
    await s.flush()


async def page(s: AsyncSession, user_id: uuid.UUID, cursor: uuid.UUID | None, limit: int) -> list[Notification]:
    q = select(Notification).where(Notification.user_id == user_id)
    if cursor:
        q = q.where(Notification.id < cursor)
    return list((await s.execute(q.order_by(Notification.id.desc()).limit(limit))).scalars().unique())


async def unread(s: AsyncSession, user_id: uuid.UUID) -> int:
    q = select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    return int((await s.execute(q)).scalar_one())


async def mark_all_read(s: AsyncSession, user_id: uuid.UUID) -> None:
    await s.execute(
        update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )


async def upsert_push(s: AsyncSession, user_id: uuid.UUID, endpoint: str, p256dh: str, auth: str) -> None:
    from app.core.ids import uuid7

    stmt = insert(PushSubscription).values(id=uuid7(), user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
    await s.execute(stmt.on_conflict_do_update(
        index_elements=["endpoint"], set_={"user_id": user_id, "p256dh": p256dh, "auth": auth}
    ))


async def delete_push(s: AsyncSession, user_id: uuid.UUID, endpoint: str) -> None:
    await s.execute(delete(PushSubscription).where(
        PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
    ))


async def delete_push_by_endpoint(s: AsyncSession, endpoint: str) -> None:
    await s.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint))


async def push_targets(s: AsyncSession, user_id: uuid.UUID) -> list[PushSubscription]:
    return list((await s.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars())
