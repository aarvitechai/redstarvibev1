import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, not_found
from app.core.events import emit
from app.core.pagination import Page, encode_cursor
from app.modules.moderation import repository as mod_repo
from app.modules.moderation.models import Report
from app.modules.moderation.schemas import ReportOut
from app.modules.moderation.service import out as report_out
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.modules.posts.models import Post
from app.modules.users import repository as users
from app.modules.users.models import User


class Stats(BaseModel):
    users: int
    posts: int
    open_reports: int


class ResolveIn(BaseModel):
    action: Literal["dismiss", "remove_content", "suspend_user"]


async def stats(s: AsyncSession) -> Stats:
    u = (await s.execute(select(func.count()).select_from(User))).scalar_one()
    p = (await s.execute(select(func.count()).select_from(Post).where(Post.deleted_at.is_(None)))).scalar_one()
    r = (await s.execute(select(func.count()).select_from(Report).where(Report.status == "open"))).scalar_one()
    return Stats(users=u, posts=p, open_reports=r)


async def queue(s: AsyncSession, cursor: uuid.UUID | None, limit: int) -> Page[ReportOut]:
    rows = await mod_repo.open_reports(s, cursor, limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(items=[report_out(r) for r in rows], next_cursor=encode_cursor(rows[-1].id) if more else None)


async def resolve(s: AsyncSession, admin: User, report_id: uuid.UUID, action: str, ip: str) -> None:
    report = await mod_repo.get(s, report_id)
    if report is None:
        raise not_found("Report")
    report.resolved_by = admin.id
    report.status = "dismissed" if action == "dismiss" else "actioned"
    removed_post = None
    target_user = None
    if report.entity_type == "post":
        post = await post_repo.get(s, report.entity_id)
        if post:
            target_user = post.author_id
            if action == "remove_content":
                post.status, post.deleted_at = "blocked", datetime.now(UTC)
                removed_post = post
    elif report.entity_type == "user":
        target_user = report.entity_id
    if action == "suspend_user" and target_user:
        user = await users.by_id(s, target_user)
        if user:
            if user.role == "superadmin" or (user.role == "admin" and admin.role != "superadmin"):
                raise forbidden("You cannot suspend this staff member")
            user.status = "suspended"
    await users.audit(s, admin.id, f"admin.report.{action}", str(report.id), ip)
    await s.commit()
    if removed_post:
        await posts.invalidate(removed_post.id)
        await emit("post.deleted", post_id=removed_post.id, author_id=removed_post.author_id)
