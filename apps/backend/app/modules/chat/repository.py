import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import Conversation, ConversationMember, Message


async def by_direct_key(s: AsyncSession, key: str) -> Conversation | None:
    return (await s.execute(select(Conversation).where(Conversation.direct_key == key))).scalar_one_or_none()


async def create(s: AsyncSession, conv: Conversation, members: dict[uuid.UUID, str]) -> None:
    s.add(conv)
    await s.flush()
    for uid, state in members.items():
        s.add(ConversationMember(conversation_id=conv.id, user_id=uid, state=state))
    await s.flush()


async def member_states(s: AsyncSession, conv_id: uuid.UUID) -> dict[uuid.UUID, str]:
    q = select(ConversationMember.user_id, ConversationMember.state).where(ConversationMember.conversation_id == conv_id)
    return {r[0]: r[1] for r in await s.execute(q)}


async def set_state(s: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID, state: str) -> None:
    await s.execute(
        update(ConversationMember)
        .where(ConversationMember.conversation_id == conv_id, ConversationMember.user_id == user_id)
        .values(state=state)
    )


async def add_member(s: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID, state: str) -> None:
    await s.execute(
        insert(ConversationMember).values(conversation_id=conv_id, user_id=user_id, state=state)
        .on_conflict_do_update(index_elements=["conversation_id", "user_id"], set_={"state": state})
    )


async def remove_member(s: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await s.execute(delete(ConversationMember).where(
        ConversationMember.conversation_id == conv_id, ConversationMember.user_id == user_id
    ))


async def sent_count(s: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID) -> int:
    q = select(func.count()).select_from(Message).where(Message.conversation_id == conv_id, Message.sender_id == user_id)
    return int((await s.execute(q)).scalar_one())


async def message_in(s: AsyncSession, conv_id: uuid.UUID, message_id: uuid.UUID) -> Message | None:
    q = select(Message).where(Message.conversation_id == conv_id, Message.id == message_id)
    return (await s.execute(q)).scalars().first()


async def get(s: AsyncSession, conv_id: uuid.UUID) -> Conversation | None:
    return await s.get(Conversation, conv_id)


async def members(s: AsyncSession, conv_ids: Sequence[uuid.UUID]) -> list[ConversationMember]:
    if not conv_ids:
        return []
    q = select(ConversationMember).where(ConversationMember.conversation_id.in_(conv_ids))
    return list((await s.execute(q)).scalars())


async def member_ids(s: AsyncSession, conv_id: uuid.UUID) -> list[uuid.UUID]:
    q = select(ConversationMember.user_id).where(ConversationMember.conversation_id == conv_id)
    return list((await s.execute(q)).scalars())


async def list_for_user(s: AsyncSession, user_id: uuid.UUID, state: str = "active", limit: int = 50) -> list[Conversation]:
    q = (
        select(Conversation)
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(ConversationMember.user_id == user_id, ConversationMember.state == state)
        .order_by(Conversation.last_message_at.desc()).limit(limit)
    )
    return list((await s.execute(q)).scalars())


async def add_message(s: AsyncSession, message: Message) -> None:
    message.created_at = datetime.now(UTC)
    s.add(message)
    await s.execute(
        update(Conversation).where(Conversation.id == message.conversation_id)
        .values(last_message_at=message.created_at)
    )
    await s.flush()


async def messages(s: AsyncSession, conv_id: uuid.UUID, cursor: uuid.UUID | None, limit: int) -> list[Message]:
    q = select(Message).where(Message.conversation_id == conv_id)
    if cursor:
        q = q.where(Message.id < cursor)
    return list((await s.execute(q.order_by(Message.id.desc()).limit(limit))).scalars())


async def last_message(s: AsyncSession, conv_id: uuid.UUID) -> Message | None:
    q = select(Message).where(Message.conversation_id == conv_id).order_by(Message.id.desc()).limit(1)
    return (await s.execute(q)).scalar_one_or_none()


async def unread_count(s: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID, since: datetime | None) -> int:
    q = select(func.count()).select_from(Message).where(Message.conversation_id == conv_id, Message.sender_id != user_id)
    if since:
        q = q.where(Message.created_at > since)
    return int((await s.execute(q)).scalar_one())


async def mark(s: AsyncSession, conv_id: uuid.UUID, user_id: uuid.UUID, field: str) -> datetime:
    now = datetime.now(UTC)
    await s.execute(
        update(ConversationMember)
        .where(ConversationMember.conversation_id == conv_id, ConversationMember.user_id == user_id)
        .values({field: now})
    )
    return now


async def sender_of(s: AsyncSession, message_id: uuid.UUID) -> uuid.UUID | None:
    return (await s.execute(select(Message.sender_id).where(Message.id == message_id))).scalar_one_or_none()
