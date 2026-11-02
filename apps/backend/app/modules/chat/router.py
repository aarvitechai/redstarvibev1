import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db
from app.core.pagination import Page, id_cursor
from app.modules.chat import service
from app.modules.chat.schemas import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MemberIn,
    MessageIn,
    MessageOut,
    TranslateIn,
    TranslateOut,
)

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.post("", response_model=ConversationOut, status_code=201)
async def create(data: ConversationCreate, me: CurrentUser, s: Db) -> ConversationOut:
    return await service.create_conversation(s, me, data)


@router.get("", response_model=list[ConversationOut])
async def list_all(me: CurrentUser, s: Db, folder: Literal["inbox", "requests"] = "inbox") -> list[ConversationOut]:
    return await service.list_conversations(s, me, folder)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get(conversation_id: uuid.UUID, me: CurrentUser, s: Db) -> ConversationOut:
    return await service.get_conversation(s, me, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def rename(conversation_id: uuid.UUID, data: ConversationUpdate, me: CurrentUser, s: Db) -> ConversationOut:
    return await service.rename_group(s, me, conversation_id, data.title)


@router.post("/{conversation_id}/accept", status_code=204)
async def accept(conversation_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.accept_request(s, me, conversation_id)


@router.post("/{conversation_id}/decline", status_code=204)
async def decline(conversation_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.decline_request(s, me, conversation_id)


@router.post("/{conversation_id}/members", status_code=204)
async def add_member(conversation_id: uuid.UUID, data: MemberIn, me: CurrentUser, s: Db) -> None:
    await service.add_group_member(s, me, conversation_id, data.username)


@router.post("/{conversation_id}/leave", status_code=204)
async def leave(conversation_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.leave_group(s, me, conversation_id)


@router.post("/{conversation_id}/messages/{message_id}/translate", response_model=TranslateOut)
async def translate(conversation_id: uuid.UUID, message_id: uuid.UUID, data: TranslateIn, me: CurrentUser, s: Db) -> TranslateOut:
    return await service.translate(s, me, conversation_id, message_id, data.language)


@router.get("/{conversation_id}/messages", response_model=Page[MessageOut])
async def messages(
    conversation_id: uuid.UUID, me: CurrentUser, s: Db, cursor: str | None = None, limit: int = Query(30, ge=1, le=100)
) -> Page[MessageOut]:
    return await service.list_messages(s, me, conversation_id, id_cursor(cursor), limit)


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201)
async def send(conversation_id: uuid.UUID, data: MessageIn, me: CurrentUser, s: Db) -> MessageOut:
    return await service.send(s, me, conversation_id, data)


@router.post("/{conversation_id}/seen", status_code=204)
async def seen(conversation_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.mark_seen(s, me, conversation_id)
