import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, Db
from app.modules.calls import service
from app.modules.calls.schemas import CallCreate, CallJoin, LiveCreate, LiveOut

router = APIRouter(tags=["calls"])


@router.post("/calls", response_model=CallJoin, status_code=201)
async def start(data: CallCreate, me: CurrentUser, s: Db) -> CallJoin:
    return await service.start_call(s, me, data)


@router.post("/calls/rooms/{room}/join", response_model=CallJoin)
async def join(room: str, me: CurrentUser, s: Db) -> CallJoin:
    return await service.join_room(s, me, room)


@router.post("/calls/{call_id}/decline", status_code=204)
async def decline(call_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.decline(s, me, call_id)


@router.post("/calls/{call_id}/end", status_code=204)
async def end(call_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.end(s, me, call_id)


@router.post("/live", response_model=CallJoin, status_code=201)
async def start_live(data: LiveCreate, me: CurrentUser, s: Db) -> CallJoin:
    return await service.start_live(s, me, data.title)


@router.get("/live", response_model=list[LiveOut])
async def list_live(me: CurrentUser, s: Db) -> list[LiveOut]:
    return await service.list_live(s, me)


@router.post("/live/{call_id}/end", status_code=204)
async def end_live(call_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.end_live(s, me, call_id)
