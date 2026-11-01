"""FastAPI only issues short lived LiveKit tokens. Media flows peer to the SFU, never through the API."""
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from livekit import api as lk
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.events import enqueue
from app.core.rate_limit import hit
from app.modules.calls import repository as repo
from app.modules.calls.models import Call
from app.modules.calls.schemas import CallCreate, CallJoin, LiveOut
from app.modules.chat import repository as chat
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.realtime.pubsub import publish_user

MAX_VIDEO_MEMBERS = 8
MAX_AUDIO_MEMBERS = 32
TOKEN_TTL = timedelta(minutes=5)


def _token(user: User, room: str, can_publish: bool) -> str:
    grants = lk.VideoGrants(room_join=True, room=room, can_publish=can_publish, can_subscribe=True, can_publish_data=True)
    return (
        lk.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(str(user.id)).with_name(user.username).with_ttl(TOKEN_TTL).with_grants(grants).to_jwt()
    )


def _join(call: Call, user: User, can_publish: bool = True) -> CallJoin:
    return CallJoin(
        call_id=call.id, room=call.room, kind=call.kind, token=_token(user, call.room, can_publish),
        url=settings.livekit_url, can_publish=can_publish,
    )


async def start_call(s: AsyncSession, me: User, data: CallCreate) -> CallJoin:
    await hit(f"call:user:{me.id}", 30, 3600)
    members = await chat.member_ids(s, data.conversation_id)
    if me.id not in members:
        raise not_found("Conversation")
    limit = MAX_VIDEO_MEMBERS if data.kind == "video" else MAX_AUDIO_MEMBERS
    if len(members) > limit:
        raise bad_request("too_many_members", f"{data.kind.title()} calls support up to {limit} people")
    others = [m for m in members if m != me.id]
    if len(members) == 2 and await users.is_blocked_either_way(s, me.id, others[0]):
        raise forbidden("You cannot call this person")
    call = Call(
        room=f"call-{secrets.token_urlsafe(12)}", kind=data.kind, host_id=me.id,
        conversation_id=data.conversation_id, status="ringing",
    )
    await repo.add(s, call, members)
    await s.commit()
    payload = {
        "type": "call", "call_id": str(call.id), "room": call.room, "kind": call.kind,
        "from": user_service.brief(me).model_dump(mode="json"),
    }
    for uid in others:
        await publish_user(uid, payload)
        await enqueue("notifications.push_call", uid, me.username, call.room)
    return _join(call, me)


async def join_room(s: AsyncSession, me: User, room: str) -> CallJoin:
    call = await repo.by_room(s, room)
    if call is None or call.status in {"ended", "declined"}:
        raise not_found("Call")
    if call.kind == "live":
        host = await users.by_id(s, call.host_id)
        if host is None or not await user_service.can_view_content_of(s, me, host):
            raise not_found("Call")
        return _join(call, me, can_publish=me.id == call.host_id)
    if not await repo.is_member(s, call.id, me.id):
        raise not_found("Call")
    if call.status == "ringing" and me.id != call.host_id:
        call.status = "active"
        await s.commit()
    return _join(call, me)


async def _member_call(s: AsyncSession, me: User, call_id: uuid.UUID) -> Call:
    call = await repo.get(s, call_id)
    if call is None or not await repo.is_member(s, call_id, me.id):
        raise not_found("Call")
    return call


async def decline(s: AsyncSession, me: User, call_id: uuid.UUID) -> None:
    call = await _member_call(s, me, call_id)
    if call.status == "ringing":
        call.status, call.ended_at = "declined", datetime.now(UTC)
        await s.commit()
        await publish_user(call.host_id, {"type": "call_declined", "call_id": str(call.id)})


async def end(s: AsyncSession, me: User, call_id: uuid.UUID) -> None:
    call = await _member_call(s, me, call_id)
    if call.status in {"ended", "declined"}:
        return
    call.status, call.ended_at = "ended", datetime.now(UTC)
    await s.commit()
    for uid in await repo.member_ids(s, call.id):
        await publish_user(uid, {"type": "call_ended", "call_id": str(call.id)})


async def start_live(s: AsyncSession, me: User, title: str) -> CallJoin:
    await hit(f"live:user:{me.id}", 10, 3600)
    call = Call(room=f"live-{secrets.token_urlsafe(12)}", kind="live", host_id=me.id, title=title, status="active")
    await repo.add(s, call, [me.id])
    await s.commit()
    await enqueue("notifications.live_started", me.id, call.room)
    return _join(call, me, can_publish=True)


async def list_live(s: AsyncSession, me: User) -> list[LiveOut]:
    calls = await repo.live_from_following(s, me.id)
    hosts = await users.by_ids(s, [c.host_id for c in calls])
    return [
        LiveOut(id=c.id, title=c.title, host=user_service.brief(hosts[c.host_id]), room=c.room)
        for c in calls if c.host_id in hosts
    ]


async def end_live(s: AsyncSession, me: User, call_id: uuid.UUID) -> None:
    call = await repo.get(s, call_id)
    if call is None or call.kind != "live":
        raise not_found("Live")
    if call.host_id != me.id:
        raise forbidden("Only the host can end this live")
    if call.status == "ended":
        raise conflict("already_ended", "This live has ended")
    call.status, call.ended_at = "ended", datetime.now(UTC)
    await s.commit()
