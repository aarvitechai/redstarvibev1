"""MCP tools call the same service layer as the REST API, so the same permission checks apply."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter

from app.ai.rag.retriever import retrieve
from app.core.database import SessionLocal
from app.core.errors import AppError, not_found
from app.core.rate_limit import hit
from app.modules.moderation.schemas import ReportIn
from app.modules.moderation.service import create_report
from app.modules.notifications import service as notifications
from app.modules.posts import service as posts
from app.modules.posts.schemas import PostCreate
from app.modules.search import service as search
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User

WRITE_LIMIT = (30, 3600)


async def _user(s: Any, user_id: uuid.UUID) -> User:
    user = await users.by_id(s, user_id)
    if user is None or user.status != "active":
        raise AppError(401, "account_inactive", "This account is not active")
    return user


async def _write_guard(s: Any, user: User, tool: str, target: str | None) -> None:
    await hit(f"mcp_write:{user.id}", *WRITE_LIMIT)
    await users.audit(s, user.id, f"mcp.{tool}", target)


async def search_posts(user_id: uuid.UUID, query: str, limit: int = 10) -> dict[str, Any]:
    async with SessionLocal() as s:
        user = await _user(s, user_id)
        found = await search.search_posts(s, user, query, min(limit, 25))
        own = await retrieve(s, user.id, query, 5)
        return {
            "posts": [
                {"id": str(p.id), "author": p.author.username, "caption": p.caption, "likes": p.like_count,
                 "created_at": p.created_at.isoformat()} for p in found
            ],
            "own_content": [{"title": c.title, "text": c.text[:400]} for c in own if c.entity_type != "help"],
        }


async def get_profile(user_id: uuid.UUID, username: str | None = None) -> dict[str, Any]:
    async with SessionLocal() as s:
        user = await _user(s, user_id)
        target = await user_service.get_visible_user(s, user, username or user.username)
        out = await user_service.profile_out(s, user, target)
        return out.model_dump(mode="json")


async def get_post_insights(user_id: uuid.UUID, post_id: str) -> dict[str, Any]:
    async with SessionLocal() as s:
        user = await _user(s, user_id)
        return (await posts.insights(s, user, uuid.UUID(post_id))).model_dump(mode="json")


async def draft_post(
    user_id: uuid.UUID, asset_ids: list[str], caption: str = "", location: str | None = None
) -> dict[str, Any]:
    """Creates a draft only. It is never auto published."""
    async with SessionLocal() as s:
        user = await _user(s, user_id)
        await _write_guard(s, user, "draft_post", None)
        data = PostCreate(asset_ids=[uuid.UUID(a) for a in asset_ids], caption=caption, location=location, draft=True)
        return (await posts.create_post(s, user, data, None)).model_dump(mode="json")


async def schedule_post(user_id: uuid.UUID, post_id: str, publish_at: str, user_confirmed: bool) -> dict[str, Any]:
    if not user_confirmed:
        return {"scheduled": False, "detail": "Ask the user to confirm the time, then call again with user_confirmed=true."}
    when = TypeAdapter(datetime).validate_python(publish_at)
    async with SessionLocal() as s:
        user = await _user(s, user_id)
        await _write_guard(s, user, "schedule_post", post_id)
        out = await posts.schedule_draft(s, user, uuid.UUID(post_id), when)
        return {"scheduled": True, "post": out.model_dump(mode="json")}


async def list_notifications(user_id: uuid.UUID, limit: int = 20) -> dict[str, Any]:
    async with SessionLocal() as s:
        user = await _user(s, user_id)
        page = await notifications.list_page(s, user, None, min(limit, 50))
        return {"items": [n.model_dump(mode="json") for n in page.items]}


async def report_content(
    user_id: uuid.UUID, entity_type: str, entity_id: str, reason: str, details: str | None = None
) -> dict[str, Any]:
    async with SessionLocal() as s:
        user = await _user(s, user_id)
        await _write_guard(s, user, "report_content", entity_id)
        data = ReportIn(entity_type=entity_type, entity_id=uuid.UUID(entity_id), reason=reason, details=details)
        try:
            return (await create_report(s, user, data)).model_dump(mode="json")
        except AppError as exc:
            if exc.code == "not_found":
                raise not_found("Content") from exc
            raise
