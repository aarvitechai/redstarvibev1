import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken
from app.modules.users.models import User


async def add_refresh(s: AsyncSession, token: RefreshToken) -> None:
    s.add(token)


async def refresh_by_hash(s: AsyncSession, token_hash: str) -> RefreshToken | None:
    q = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    return (await s.execute(q)).scalar_one_or_none()


async def revoke_family(s: AsyncSession, family_id: uuid.UUID) -> None:
    await s.execute(
        update(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all(s: AsyncSession, user_id: uuid.UUID) -> None:
    await s.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def by_google_sub(s: AsyncSession, sub: str) -> User | None:
    return (await s.execute(select(User).where(User.google_sub == sub))).scalars().first()
