from fastapi import APIRouter

from app.api.deps import CurrentUser, Db
from app.modules.moderation import service
from app.modules.moderation.schemas import ReportIn, ReportOut

router = APIRouter(tags=["moderation"])


@router.post("/reports", response_model=ReportOut, status_code=201)
async def report(data: ReportIn, me: CurrentUser, s: Db) -> ReportOut:
    return await service.create_report(s, me, data)
