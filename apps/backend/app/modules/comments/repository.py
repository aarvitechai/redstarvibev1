import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments.models import Comment


async def add(s: AsyncSession, comment: Comment) -> None:
    s.add(comment)
    await s.flush()
    await s.refresh(comment, ["created_at"])


async def get(s: AsyncSession, comment_id: uuid.UUID) -> Comment | None:
    q = select(Comment).where(Comment.id == comment_id, Comment.deleted_at.is_(None))
    return (await s.execute(q)).scalars().first()


async def list_for_post(
    s: AsyncSession, post_id: uuid.UUID, parent_id: uuid.UUID | None, cursor: uuid.UUID | None, limit: int,
    hidden_authors: set[uuid.UUID],
) -> list[Comment]:
    q = select(Comment).where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
    q = q.where(Comment.parent_id == parent_id if parent_id else Comment.parent_id.is_(None))
    if hidden_authors:
        q = q.where(Comment.author_id.not_in(hidden_authors))
    if cursor:
        q = q.where(Comment.id < cursor)
    return list((await s.execute(q.order_by(Comment.id.desc()).limit(limit))).scalars().unique())


async def bump_replies(s: AsyncSession, comment_id: uuid.UUID, delta: int) -> None:
    await s.execute(update(Comment).where(Comment.id == comment_id).values(reply_count=Comment.reply_count + delta))
