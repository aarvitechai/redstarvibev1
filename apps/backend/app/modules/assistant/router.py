from fastapi import APIRouter

from app.api.deps import CurrentUser, Db
from app.modules.assistant import service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/assistant", response_model=service.AskOut)
async def assistant(data: service.AskIn, me: CurrentUser, s: Db) -> service.AskOut:
    return await service.ask(s, me, data.question)


@router.post("/caption", response_model=service.CaptionOut)
async def caption(data: service.CaptionIn, me: CurrentUser, s: Db) -> service.CaptionOut:
    return await service.suggest_caption(s, me, data.asset_id)


@router.get("/insights", response_model=service.InsightsOut)
async def insights(me: CurrentUser, s: Db) -> service.InsightsOut:
    return await service.creator_insights(s, me)
