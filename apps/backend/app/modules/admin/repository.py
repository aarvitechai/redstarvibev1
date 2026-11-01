import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import TestDataBatch
from app.modules.follows.models import Follow
from app.modules.moderation.models import Report
from app.modules.notifications.models import Notification
from app.modules.posts.models import Post
from app.modules.search.repository import _escape
from app.modules.users.models import User


async def add_batch(s: AsyncSession, batch: TestDataBatch) -> None:
    s.add(batch)
    await s.flush()
    await s.refresh(batch, ["created_at"])


async def get_batch(s: AsyncSession, batch_id: uuid.UUID) -> TestDataBatch | None:
    return await s.get(TestDataBatch, batch_id)


async def list_batches(s: AsyncSession, limit: int = 100) -> list[TestDataBatch]:
    q = select(TestDataBatch).order_by(TestDataBatch.id.desc()).limit(limit)
    return list((await s.execute(q)).scalars())


async def removable_batches(s: AsyncSession) -> list[TestDataBatch]:
    q = select(TestDataBatch).where(TestDataBatch.status.in_(["ready", "failed"]))
    return list((await s.execute(q)).scalars())


async def batch_user_ids(s: AsyncSession, batch_id: uuid.UUID) -> list[uuid.UUID]:
    """The only source of what gets deleted: accounts explicitly stamped with this batch."""
    q = select(User.id).where(User.test_batch_id == batch_id)
    return list((await s.execute(q)).scalars())


async def post_ids_of(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list((await s.execute(select(Post.id).where(Post.author_id == user_id))).scalars())


async def follower_ids(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list((await s.execute(select(Follow.follower_id).where(Follow.followee_id == user_id))).scalars())


async def delete_references(s: AsyncSession, user_id: uuid.UUID, post_ids: list[uuid.UUID]) -> None:
    """Notifications and reports hold plain ids, so nothing cascades to them."""
    from sqlalchemy import delete

    targets = [user_id, *post_ids]
    await s.execute(delete(Notification).where(Notification.entity_id.in_(post_ids)))
    await s.execute(delete(Report).where(Report.entity_id.in_(targets)))


async def find_users(s: AsyncSession, q: str, limit: int = 30) -> list[User]:
    stmt = select(User)
    if q:
        like = f"%{_escape(q)}%"
        stmt = stmt.where(or_(User.username.ilike(like, escape="\\"), User.email.ilike(like, escape="\\")))
    else:
        stmt = stmt.where(User.role != "user")
    return list((await s.execute(stmt.order_by(User.username).limit(limit))).scalars().unique())
