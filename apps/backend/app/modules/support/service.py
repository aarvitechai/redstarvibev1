"""Support tickets. Staff answer and resolve. Escalated tickets are resolved only by admins."""
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, forbidden, not_found
from app.core.pagination import Page, encode_cursor
from app.core.permissions import has_permission
from app.core.rate_limit import hit
from app.modules.notifications.service import notify
from app.modules.support.models import Ticket, TicketMessage
from app.modules.users import repository as users
from app.modules.users.models import User

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
TicketStatus = Literal["open", "escalated", "resolved"]


class TicketIn(BaseModel):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
    body: Text


class ReplyIn(BaseModel):
    body: Text


class TicketMessageOut(BaseModel):
    id: uuid.UUID
    is_staff: bool
    author: str | None
    body: str
    created_at: datetime


class TicketOut(BaseModel):
    id: uuid.UUID
    user: str
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[TicketMessageOut] = Field(default_factory=list)


async def _messages(s: AsyncSession, ticket_id: uuid.UUID, viewer_is_staff: bool) -> list[TicketMessageOut]:
    rows = list((await s.execute(
        select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.id)
    )).scalars())
    names = {uid: u.username for uid, u in (await users.by_ids(s, [m.author_id for m in rows if m.author_id])).items()}
    return [
        TicketMessageOut(
            id=m.id, is_staff=m.is_staff, body=m.body, created_at=m.created_at,
            # People see "Support", not which employee answered them.
            author="Support" if m.is_staff and not viewer_is_staff else names.get(m.author_id) if m.author_id else None,
        ) for m in rows
    ]


def _out(t: Ticket, messages: list[TicketMessageOut] | None = None) -> TicketOut:
    return TicketOut(
        id=t.id, user=t.user.username, subject=t.subject, status=t.status, created_at=t.created_at,
        updated_at=t.updated_at, messages=messages or [],
    )


def _is_staff(user: User) -> bool:
    return has_permission(user.role, "resolve_tickets")


async def _get_visible(s: AsyncSession, user: User, ticket_id: uuid.UUID) -> Ticket:
    ticket = await s.get(Ticket, ticket_id)
    if ticket is None or (ticket.user_id != user.id and not _is_staff(user)):
        raise not_found("Ticket")  # 404, not 403: do not reveal that it exists
    return ticket


async def create(s: AsyncSession, user: User, data: TicketIn) -> TicketOut:
    await hit(f"ticket:user:{user.id}", 10, 86400)
    ticket = Ticket(user_id=user.id, subject=data.subject)
    ticket.user = user
    s.add(ticket)
    await s.flush()
    s.add(TicketMessage(ticket_id=ticket.id, author_id=user.id, body=data.body))
    await s.commit()
    return await detail(s, user, ticket.id)


async def detail(s: AsyncSession, user: User, ticket_id: uuid.UUID) -> TicketOut:
    ticket = await _get_visible(s, user, ticket_id)
    return _out(ticket, await _messages(s, ticket.id, _is_staff(user)))


async def mine(s: AsyncSession, user: User) -> list[TicketOut]:
    q = select(Ticket).where(Ticket.user_id == user.id).order_by(Ticket.id.desc()).limit(100)
    return [_out(t) for t in (await s.execute(q)).scalars().unique()]


async def queue(s: AsyncSession, status: TicketStatus, cursor: uuid.UUID | None, limit: int) -> Page[TicketOut]:
    q = select(Ticket).where(Ticket.status == status)
    q = q.where(Ticket.id > cursor) if cursor else q
    rows = list((await s.execute(q.order_by(Ticket.id).limit(limit + 1))).scalars().unique())
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(items=[_out(t) for t in rows], next_cursor=encode_cursor(rows[-1].id) if more else None)


async def reply(s: AsyncSession, user: User, ticket_id: uuid.UUID, data: ReplyIn, ip: str | None) -> TicketOut:
    await hit(f"ticket_reply:user:{user.id}", 120, 3600)
    ticket = await _get_visible(s, user, ticket_id)
    from_owner = ticket.user_id == user.id
    from_staff = not from_owner
    s.add(TicketMessage(ticket_id=ticket.id, author_id=user.id, is_staff=from_staff, body=data.body))
    ticket.updated_at = datetime.now(UTC)
    if from_owner and ticket.status == "resolved":
        ticket.status = "open"
    if from_staff:
        await users.audit(s, user.id, "staff.ticket.reply", str(ticket.id), ip)
        await notify(s, ticket.user_id, "ticket_reply", None, ticket.id)
    await s.commit()
    return await detail(s, user, ticket.id)


async def escalate(s: AsyncSession, actor: User, ticket_id: uuid.UUID, ip: str | None) -> TicketOut:
    ticket = await _get_visible(s, actor, ticket_id)
    if ticket.status != "open":
        raise bad_request("not_open", "Only open tickets can be escalated")
    ticket.status, ticket.escalated_by, ticket.updated_at = "escalated", actor.id, datetime.now(UTC)
    await users.audit(s, actor.id, "staff.ticket.escalate", str(ticket.id), ip)
    await s.commit()
    return await detail(s, actor, ticket.id)


async def resolve(s: AsyncSession, actor: User, ticket_id: uuid.UUID, ip: str | None) -> TicketOut:
    ticket = await _get_visible(s, actor, ticket_id)
    if ticket.status == "resolved":
        raise bad_request("already_resolved", "This ticket is already resolved")
    if ticket.status == "escalated" and actor.role == "staff":
        raise forbidden("Only an admin can resolve an escalated ticket")
    ticket.status, ticket.resolved_by, ticket.updated_at = "resolved", actor.id, datetime.now(UTC)
    await users.audit(s, actor.id, "staff.ticket.resolve", str(ticket.id), ip)
    await notify(s, ticket.user_id, "ticket_resolved", None, ticket.id)
    await s.commit()
    return await detail(s, actor, ticket.id)
