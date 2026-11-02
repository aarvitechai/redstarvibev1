import uuid

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import TestDataBatch
from app.modules.chat.models import Conversation, Message
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
    q = select(TestDataBatch).where(TestDataBatch.status.in_(["ready", "disabled", "failed"]))
    return list((await s.execute(q)).scalars())


async def set_batch_user_status(s: AsyncSession, batch_id: uuid.UUID, status: str) -> None:
    """Visibility rules already check the author's status, so this hides their posts, stories and profiles everywhere."""
    await s.execute(update(User).where(User.test_batch_id == batch_id).values(status=status))


async def real_follower_ids(s: AsyncSession, batch_id: uuid.UUID) -> list[uuid.UUID]:
    in_batch = select(User.id).where(User.test_batch_id == batch_id)
    real = select(User.id).where(User.test_batch_id.is_(None))
    q = select(Follow.follower_id).where(Follow.followee_id.in_(in_batch), Follow.follower_id.in_(real)).distinct()
    return list((await s.execute(q)).scalars())


async def batch_user_ids(s: AsyncSession, batch_id: uuid.UUID) -> list[uuid.UUID]:
    """The only source of what gets deleted: accounts explicitly stamped with this batch."""
    # Newest first: in a demo set the first account owns the shared media, so it must go last.
    q = select(User.id).where(User.test_batch_id == batch_id).order_by(User.id.desc())
    return list((await s.execute(q)).scalars())


async def post_ids_of(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list((await s.execute(select(Post.id).where(Post.author_id == user_id))).scalars())


async def follower_ids(s: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list((await s.execute(select(Follow.follower_id).where(Follow.followee_id == user_id))).scalars())


async def delete_references(s: AsyncSession, user_id: uuid.UUID, post_ids: list[uuid.UUID]) -> None:
    """Notifications, reports and messages hold plain ids, so nothing cascades to them."""
    targets = [user_id, *post_ids]
    await s.execute(delete(Notification).where(Notification.entity_id.in_(post_ids)))
    await s.execute(delete(Report).where(Report.entity_id.in_(targets)))
    # Chats a test account started, including replies from real accounts, so no empty chat stays in their inbox.
    started = select(Conversation.id).where(Conversation.created_by == user_id)
    await s.execute(delete(Message).where(Message.conversation_id.in_(started)))
    await s.execute(delete(Conversation).where(Conversation.created_by == user_id))


async def find_users(s: AsyncSession, q: str, limit: int = 30) -> list[User]:
    stmt = select(User)
    if q:
        like = f"%{_escape(q)}%"
        stmt = stmt.where(or_(User.username.ilike(like, escape="\\"), User.email.ilike(like, escape="\\")))
    else:
        stmt = stmt.where(User.role != "user")
    return list((await s.execute(stmt.order_by(User.username).limit(limit))).scalars().unique())
