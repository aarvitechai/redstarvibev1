import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import uuid7
from app.modules.moderation.models import AiOutputLog, Report


async def add(s: AsyncSession, report: Report) -> None:
    s.add(report)
    await s.flush()
    await s.refresh(report, ["created_at"])


async def get(s: AsyncSession, report_id: uuid.UUID) -> Report | None:
    return await s.get(Report, report_id)


async def open_reports(s: AsyncSession, cursor: uuid.UUID | None, limit: int) -> list[Report]:
    q = select(Report).where(Report.status == "open")
    if cursor:
        q = q.where(Report.id > cursor)
    return list((await s.execute(q.order_by(Report.id.asc()).limit(limit))).scalars())


async def log_ai(
    s: AsyncSession, kind: str, entity_id: uuid.UUID | None, user_id: uuid.UUID | None, model: str, output: str,
    meta: dict[str, object] | None = None,
) -> None:
    await s.execute(insert(AiOutputLog).values(
        id=uuid7(), kind=kind, entity_id=entity_id, user_id=user_id, model=model, output=output, meta=meta
    ))
