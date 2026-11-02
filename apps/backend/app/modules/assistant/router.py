import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, Db
from app.modules.assistant import service, suggestions

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/assistant", response_model=service.AskOut)
async def assistant(data: service.AskIn, me: CurrentUser, s: Db) -> service.AskOut:
    return await service.ask(s, me, data.question)


@router.get("/features", response_model=suggestions.Features)
async def features() -> suggestions.Features:
    return suggestions.features()


@router.get("/captions/{asset_id}", response_model=suggestions.CaptionsOut)
async def captions(asset_id: uuid.UUID, me: CurrentUser, s: Db) -> suggestions.CaptionsOut:
    return await suggestions.captions(s, me, asset_id)


@router.post("/rewrite", response_model=suggestions.RewriteOut)
async def rewrite(data: suggestions.RewriteIn, me: CurrentUser) -> suggestions.RewriteOut:
    return await suggestions.rewrite(me, data)


@router.post("/hashtags", response_model=suggestions.HashtagsOut)
async def hashtags(data: suggestions.HashtagsIn, me: CurrentUser) -> suggestions.HashtagsOut:
    return await suggestions.hashtags(me, data)


@router.post("/comment-check", response_model=suggestions.CommentCheckOut)
async def comment_check(data: suggestions.CommentCheckIn, me: CurrentUser) -> suggestions.CommentCheckOut:
    return await suggestions.check_comment(me, data)


@router.get("/insights", response_model=service.InsightsOut)
async def insights(me: CurrentUser, s: Db) -> service.InsightsOut:
    return await service.creator_insights(s, me)
