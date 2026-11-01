import uuid

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db, OptionalUser
from app.core.pagination import Page, id_cursor
from app.modules.comments import service
from app.modules.comments.schemas import CommentIn, CommentOut

router = APIRouter(tags=["comments"])


@router.get("/posts/{post_id}/comments", response_model=Page[CommentOut])
async def list_comments(
    post_id: uuid.UUID, viewer: OptionalUser, s: Db, parent_id: uuid.UUID | None = None,
    cursor: str | None = None, limit: int = Query(20, ge=1, le=50),
) -> Page[CommentOut]:
    return await service.list_comments(s, viewer, post_id, parent_id, id_cursor(cursor), limit)


@router.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=201)
async def create(post_id: uuid.UUID, data: CommentIn, me: CurrentUser, s: Db) -> CommentOut:
    return await service.create(s, me, post_id, data)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete(comment_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.delete(s, me, comment_id)
