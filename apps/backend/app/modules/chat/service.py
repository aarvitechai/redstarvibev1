"""Messages are stored in Postgres first, then delivered. Client acks give delivered and seen."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, forbidden, not_found
from app.core.events import emit
from app.core.pagination import Page, encode_cursor
from app.core.rate_limit import hit
from app.modules.chat import repository as repo
from app.modules.chat.models import Conversation, Message
from app.modules.chat.schemas import ConversationCreate, ConversationOut, MemberState, MessageIn, MessageOut
from app.modules.follows import repository as follows
from app.modules.media import repository as media_repo
from app.modules.media.service import asset_out
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.realtime.pubsub import is_online, publish_user


async def member_ids_if_member(s: AsyncSession, user_id: uuid.UUID, conv_id: uuid.UUID) -> list[uuid.UUID] | None:
    ids = await repo.member_ids(s, conv_id)
    return ids if user_id in ids else None


async def _require_member(s: AsyncSession, user: User, conv_id: uuid.UUID) -> list[uuid.UUID]:
    ids = await member_ids_if_member(s, user.id, conv_id)
    if ids is None:
        raise not_found("Conversation")  # do not reveal that it exists
    return ids


async def _message_out(s: AsyncSession, m: Message) -> MessageOut:
    media = None
    if m.asset_id:
        asset = await media_repo.get(s, m.asset_id)
        media = asset_out(asset) if asset else None
    return MessageOut(
        id=m.id, conversation_id=m.conversation_id, sender_id=m.sender_id, body=m.body,
        media=media, created_at=m.created_at,
    )


async def _conversation_out(s: AsyncSession, me: User, conv: Conversation) -> ConversationOut:
    rows = await repo.members(s, [conv.id])
    people = await users.by_ids(s, [r.user_id for r in rows])
    mine = next(r for r in rows if r.user_id == me.id)
    last = await repo.last_message(s, conv.id)
    states = []
    for r in rows:
        if r.user_id in people:
            states.append(MemberState(
                user=user_service.brief(people[r.user_id]), last_delivered_at=r.last_delivered_at,
                last_seen_at=r.last_seen_at, online=await is_online(r.user_id),
            ))
    return ConversationOut(
        id=conv.id, is_group=conv.is_group, title=conv.title, members=states,
        last_message=await _message_out(s, last) if last else None, last_message_at=conv.last_message_at,
        unread=await repo.unread_count(s, conv.id, me.id, mine.last_seen_at),
    )


async def create_conversation(s: AsyncSession, me: User, data: ConversationCreate) -> ConversationOut:
    others = await users.by_usernames(s, [u for u in data.usernames if u.lower() != me.username.lower()])
    if not others or len(others) != len({u.lower() for u in data.usernames if u.lower() != me.username.lower()}):
        raise not_found("User")
    for other in others:
        if other.status != "active" or await users.is_blocked_either_way(s, me.id, other.id):
            raise forbidden(f"You cannot message {other.username}")
        # Private accounts only accept messages from people they follow or who follow them.
        if other.is_private:
            a = await follows.status_of(s, me.id, other.id)
            b = await follows.status_of(s, other.id, me.id)
            if "active" not in {a, b}:
                raise forbidden(f"{other.username} only accepts messages from followers")
    is_group = len(others) > 1
    key = None
    if not is_group:
        key = ":".join(sorted([me.id.hex, others[0].id.hex]))[:80]
        existing = await repo.by_direct_key(s, key[:80])
        if existing:
            return await _conversation_out(s, me, existing)
    conv = Conversation(is_group=is_group, title=data.title if is_group else None, direct_key=key, created_by=me.id)
    await repo.create(s, conv, [me.id, *[o.id for o in others]])
    await s.commit()
    return await _conversation_out(s, me, conv)


async def list_conversations(s: AsyncSession, me: User) -> list[ConversationOut]:
    return [await _conversation_out(s, me, c) for c in await repo.list_for_user(s, me.id)]


async def get_conversation(s: AsyncSession, me: User, conv_id: uuid.UUID) -> ConversationOut:
    await _require_member(s, me, conv_id)
    conv = await repo.get(s, conv_id)
    if conv is None:
        raise not_found("Conversation")
    return await _conversation_out(s, me, conv)


async def list_messages(
    s: AsyncSession, me: User, conv_id: uuid.UUID, cursor: uuid.UUID | None, limit: int
) -> Page[MessageOut]:
    await _require_member(s, me, conv_id)
    rows = await repo.messages(s, conv_id, cursor, limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[await _message_out(s, m) for m in rows],
        next_cursor=encode_cursor(rows[-1].id) if more else None,
    )


async def send(s: AsyncSession, me: User, conv_id: uuid.UUID, data: MessageIn) -> MessageOut:
    await hit(f"dm:user:{me.id}", 120, 60)
    members = await _require_member(s, me, conv_id)
    body = data.body.strip()
    if not body and not data.asset_id:
        raise bad_request("empty_message", "Write something first")
    conv = await repo.get(s, conv_id)
    if conv and not conv.is_group:
        other = next((m for m in members if m != me.id), None)
        if other and await users.is_blocked_either_way(s, me.id, other):
            raise forbidden("You cannot message this person")
    media_key = None
    if data.asset_id:
        asset = await media_repo.get(s, data.asset_id)
        if asset is None or asset.owner_id != me.id or asset.status != "ready":
            raise bad_request("media_not_ready", "That upload is not ready yet")
        media_key = asset.raw_key
    message = Message(conversation_id=conv_id, sender_id=me.id, body=body, asset_id=data.asset_id, media_key=media_key)
    await repo.add_message(s, message)
    await repo.mark(s, conv_id, me.id, "last_seen_at")
    await s.commit()  # stored first
    out = await _message_out(s, message)
    payload = {"type": "message", "message": out.model_dump(mode="json")}
    for member in members:
        await publish_user(member, payload)
    await emit("message.created", message_id=out.id, conversation_id=conv_id, sender_id=me.id)
    return out


async def mark_seen(s: AsyncSession, me: User, conv_id: uuid.UUID) -> None:
    members = await _require_member(s, me, conv_id)
    when = await repo.mark(s, conv_id, me.id, "last_seen_at")
    await s.commit()
    for member in members:
        if member != me.id:
            await publish_user(member, {
                "type": "seen", "conversation_id": str(conv_id), "user_id": str(me.id), "at": when.isoformat(),
            })


async def mark_delivered(s: AsyncSession, user_id: uuid.UUID, conv_id: uuid.UUID) -> None:
    await repo.mark(s, conv_id, user_id, "last_delivered_at")
    await s.commit()
