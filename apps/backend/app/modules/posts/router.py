import re
import uuid

from fastapi import APIRouter, Header, Query, Request, Response

from app.api.deps import CurrentUser, Db, OptionalUser
from app.core.config import settings
from app.core.pagination import Page, id_cursor
from app.core.rate_limit import client_ip
from app.modules.posts import repository as repo
from app.modules.posts import service
from app.modules.posts.schemas import (
    BestTimes,
    CollectionIn,
    CollectionOut,
    Insights,
    LikeResult,
    PostCreate,
    PostOut,
    PostUpdate,
    SaveIn,
    ScheduleRequest,
    ViewResult,
)

VISITOR_COOKIE = "rsv_visitor"
VISITOR_RE = re.compile(r"[0-9a-f]{32}")

router = APIRouter(tags=["posts"])


@router.post("/posts", response_model=PostOut, status_code=201)
async def create(
    data: PostCreate, me: CurrentUser, s: Db, idempotency_key: str | None = Header(None, max_length=100)
) -> PostOut:
    return await service.create_post(s, me, data, idempotency_key)


@router.get("/posts/best-times", response_model=BestTimes)
async def best_times(me: CurrentUser, s: Db, tz: str = Query("UTC", max_length=60)) -> BestTimes:
    return await service.best_times(s, me, tz)


@router.get("/posts/schedule-requests", response_model=list[ScheduleRequest])
async def schedule_requests(me: CurrentUser, s: Db) -> list[ScheduleRequest]:
    return await service.schedule_requests(s, me)


@router.post("/posts/{post_id}/schedule-request", response_model=PostOut)
async def approve_schedule_request(post_id: uuid.UUID, me: CurrentUser, s: Db) -> PostOut:
    return await service.approve_schedule(s, me, post_id)


@router.delete("/posts/{post_id}/schedule-request", status_code=204)
async def decline_schedule_request(post_id: uuid.UUID, me: CurrentUser) -> None:
    await service.decline_schedule(me, post_id)


@router.get("/posts/drafts", response_model=list[PostOut])
async def drafts(me: CurrentUser, s: Db) -> list[PostOut]:
    ids = await repo.own_posts_by_status(s, me.id, ["draft", "scheduled", "processing", "failed", "blocked"])
    return await service.hydrate(s, me, ids)


@router.get("/posts/{post_id}", response_model=PostOut)
async def get_post(post_id: uuid.UUID, viewer: OptionalUser, s: Db) -> PostOut:
    return await service.get_post(s, viewer, post_id)


@router.patch("/posts/{post_id}", response_model=PostOut)
async def update(post_id: uuid.UUID, data: PostUpdate, me: CurrentUser, s: Db) -> PostOut:
    return await service.update_post(s, me, post_id, data)


@router.delete("/posts/{post_id}", status_code=204)
async def delete(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.delete_post(s, me, post_id)


@router.post("/posts/{post_id}/publish", response_model=PostOut)
async def publish(post_id: uuid.UUID, me: CurrentUser, s: Db) -> PostOut:
    return await service.publish_draft(s, me, post_id)


@router.delete("/posts/{post_id}/tags/me", status_code=204)
async def remove_my_tag(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.remove_my_tag(s, me, post_id)


@router.get("/collab-requests", response_model=list[PostOut])
async def collab_requests(me: CurrentUser, s: Db) -> list[PostOut]:
    return await service.collab_requests(s, me)


@router.post("/posts/{post_id}/collab/accept", status_code=204)
async def accept_collab(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.accept_collab(s, me, post_id)


@router.delete("/posts/{post_id}/collab/me", status_code=204)
async def remove_collab(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.remove_collab(s, me, post_id)


@router.post("/posts/{post_id}/pin", status_code=204)
async def pin(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.pin(s, me, post_id)


@router.delete("/posts/{post_id}/pin", status_code=204)
async def unpin(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.unpin(s, me, post_id)


@router.post("/posts/{post_id}/like", response_model=LikeResult)
async def like(post_id: uuid.UUID, me: CurrentUser, s: Db) -> LikeResult:
    return await service.like(s, me, post_id)


@router.delete("/posts/{post_id}/like", response_model=LikeResult)
async def unlike(post_id: uuid.UUID, me: CurrentUser, s: Db) -> LikeResult:
    return await service.unlike(s, me, post_id)


@router.post("/posts/{post_id}/save", status_code=204)
async def save(post_id: uuid.UUID, data: SaveIn, me: CurrentUser, s: Db) -> None:
    await service.save(s, me, post_id, data.collection_id)


@router.delete("/posts/{post_id}/save", status_code=204)
async def unsave(post_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.unsave(s, me, post_id)


@router.post("/posts/{post_id}/view", response_model=ViewResult)
async def view(post_id: uuid.UUID, request: Request, response: Response, viewer: OptionalUser, s: Db) -> ViewResult:
    cookie = request.cookies.get(VISITOR_COOKIE, "")
    visitor = cookie if VISITOR_RE.fullmatch(cookie) else None
    result, new_visitor = await service.record_view(s, viewer, post_id, visitor, client_ip(request))
    if new_visitor:
        response.set_cookie(
            VISITOR_COOKIE, new_visitor, max_age=365 * 86400, path="/api/v1/posts", httponly=True,
            secure=settings.cookie_secure, samesite="lax", domain=settings.cookie_domain or None,
        )
    return result


@router.get("/posts/{post_id}/insights", response_model=Insights)
async def insights(post_id: uuid.UUID, me: CurrentUser, s: Db) -> Insights:
    return await service.insights(s, me, post_id)


@router.get("/saved", response_model=Page[PostOut])
async def saved(
    me: CurrentUser, s: Db, collection_id: uuid.UUID | None = None, cursor: str | None = None,
    limit: int = Query(18, ge=1, le=48),
) -> Page[PostOut]:
    return await service.saved_page(s, me, collection_id, id_cursor(cursor), limit)


@router.get("/collections", response_model=list[CollectionOut])
async def collections(me: CurrentUser, s: Db) -> list[CollectionOut]:
    return [CollectionOut(id=c.id, name=c.name) for c in await repo.collections(s, me.id)]


@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(data: CollectionIn, me: CurrentUser, s: Db) -> CollectionOut:
    return await service.create_collection(s, me, data.name)


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(collection_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.delete_collection(s, me, collection_id)
