import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import CurrentUser, Db, require_permission
from app.core.pagination import Page, id_cursor
from app.core.rate_limit import client_ip
from app.modules.support import service
from app.modules.support.service import ReplyIn, TicketIn, TicketOut, TicketStatus
from app.modules.users.models import User

router = APIRouter(tags=["support"])

TicketStaff = Annotated[User, Depends(require_permission("resolve_tickets"))]
Escalator = Annotated[User, Depends(require_permission("escalate"))]


@router.post("/support/tickets", response_model=TicketOut, status_code=201)
async def create(data: TicketIn, me: CurrentUser, s: Db) -> TicketOut:
    return await service.create(s, me, data)


@router.get("/support/tickets", response_model=list[TicketOut])
async def mine(me: CurrentUser, s: Db) -> list[TicketOut]:
    return await service.mine(s, me)


@router.get("/support/tickets/{ticket_id}", response_model=TicketOut)
async def detail(ticket_id: uuid.UUID, me: CurrentUser, s: Db) -> TicketOut:
    return await service.detail(s, me, ticket_id)


@router.post("/support/tickets/{ticket_id}/messages", response_model=TicketOut, status_code=201)
async def reply(ticket_id: uuid.UUID, data: ReplyIn, me: CurrentUser, request: Request, s: Db) -> TicketOut:
    return await service.reply(s, me, ticket_id, data, client_ip(request))


@router.get("/admin/tickets", response_model=Page[TicketOut])
async def queue(
    _: TicketStaff, s: Db, status: TicketStatus = "open", cursor: str | None = None, limit: int = Query(30, ge=1, le=100)
) -> Page[TicketOut]:
    return await service.queue(s, status, id_cursor(cursor), limit)


@router.post("/admin/tickets/{ticket_id}/escalate", response_model=TicketOut)
async def escalate(ticket_id: uuid.UUID, actor: Escalator, request: Request, s: Db) -> TicketOut:
    return await service.escalate(s, actor, ticket_id, client_ip(request))


@router.post("/admin/tickets/{ticket_id}/resolve", response_model=TicketOut)
async def resolve(ticket_id: uuid.UUID, actor: TicketStaff, request: Request, s: Db) -> TicketOut:
    return await service.resolve(s, actor, ticket_id, client_ip(request))
