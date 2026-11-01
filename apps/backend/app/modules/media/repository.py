import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.models import BlockedHash, MediaAsset


async def add(s: AsyncSession, asset: MediaAsset) -> None:
    s.add(asset)
    await s.flush()


async def get(s: AsyncSession, asset_id: uuid.UUID) -> MediaAsset | None:
    return await s.get(MediaAsset, asset_id)


async def get_owned(s: AsyncSession, ids: Sequence[uuid.UUID], owner: uuid.UUID) -> list[MediaAsset]:
    q = select(MediaAsset).where(MediaAsset.id.in_(ids), MediaAsset.owner_id == owner)
    return list((await s.execute(q)).scalars())


async def is_blocked_hash(s: AsyncSession, sha256: str) -> bool:
    return await s.get(BlockedHash, sha256) is not None
