import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calls.models import Call, CallMember
from app.modules.follows.models import Follow


async def add(s: AsyncSession, call: Call, members: Sequence[uuid.UUID]) -> None:
    s.add(call)
    await s.flush()
    for uid in members:
        s.add(CallMember(call_id=call.id, user_id=uid))


async def get(s: AsyncSession, call_id: uuid.UUID) -> Call | None:
    return await s.get(Call, call_id)


async def by_room(s: AsyncSession, room: str) -> Call | None:
    return (await s.execute(select(Call).where(Call.room == room))).scalar_one_or_none()


async def is_member(s: AsyncSession, call_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return await s.get(CallMember, (call_id, user_id)) is not None


async def member_ids(s: AsyncSession, call_id: uuid.UUID) -> list[uuid.UUID]:
    return list((await s.execute(select(CallMember.user_id).where(CallMember.call_id == call_id))).scalars())


async def live_from_following(s: AsyncSession, user_id: uuid.UUID) -> list[Call]:
    followed = select(Follow.followee_id).where(Follow.follower_id == user_id, Follow.status == "active")
    q = select(Call).where(
        Call.kind == "live", Call.status == "active", (Call.host_id.in_(followed)) | (Call.host_id == user_id)
    ).order_by(Call.id.desc()).limit(50)
    return list((await s.execute(q)).scalars())
