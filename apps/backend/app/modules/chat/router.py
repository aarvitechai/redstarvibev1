import uuid

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db
from app.core.pagination import Page, id_cursor
from app.modules.chat import service
from app.modules.chat.schemas import ConversationCreate, ConversationOut, MessageIn, MessageOut

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.post("", response_model=ConversationOut, status_code=201)
async def create(data: ConversationCreate, me: CurrentUser, s: Db) -> ConversationOut:
    return await service.create_conversation(s, me, data)


@router.get("", response_model=list[ConversationOut])
async def list_all(me: CurrentUser, s: Db) -> list[ConversationOut]:
    return await service.list_conversations(s, me)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get(conversation_id: uuid.UUID, me: CurrentUser, s: Db) -> ConversationOut:
    return await service.get_conversation(s, me, conversation_id)


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
