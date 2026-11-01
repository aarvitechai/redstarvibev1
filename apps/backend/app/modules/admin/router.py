import uuid

from fastapi import APIRouter, Query, Request

from app.api.deps import AdminUser, Db
from app.core.pagination import Page, id_cursor
from app.core.rate_limit import client_ip
from app.modules.admin import service
from app.modules.moderation.schemas import ReportOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=service.Stats)
async def stats(_: AdminUser, s: Db) -> service.Stats:
    return await service.stats(s)


@router.get("/reports", response_model=Page[ReportOut])
async def reports(_: AdminUser, s: Db, cursor: str | None = None, limit: int = Query(30, le=100)) -> Page[ReportOut]:
    return await service.queue(s, id_cursor(cursor), limit)


@router.post("/reports/{report_id}/resolve", status_code=204)
async def resolve(report_id: uuid.UUID, data: service.ResolveIn, admin: AdminUser, request: Request, s: Db) -> None:
    await service.resolve(s, admin, report_id, data.action, client_ip(request))
