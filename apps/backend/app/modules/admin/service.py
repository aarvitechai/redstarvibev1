import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import counter_incr
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.events import emit
from app.core.pagination import Page, encode_cursor
from app.modules.chat import repository as chat_repo
from app.modules.comments import repository as comment_repo
from app.modules.communities.service import get_post_for_report
from app.modules.moderation import repository as mod_repo
from app.modules.moderation.models import Report
from app.modules.moderation.schemas import ReportOut
from app.modules.moderation.service import out as report_out
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.modules.posts.models import Post
from app.modules.stories import repository as story_repo
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


async def escalate(s: AsyncSession, actor: User, report_id: uuid.UUID, ip: str) -> None:
    report = await mod_repo.get(s, report_id)
    if report is None:
        raise not_found("Report")
    if report.status != "open":
        raise conflict("already_resolved", "Someone already resolved this report")
    report.escalated_by, report.escalated_at = actor.id, datetime.now(UTC)
    await users.audit(s, actor.id, "staff.report.escalate", str(report.id), ip)
    await s.commit()


async def _remove_post(s: AsyncSession, post: Post) -> None:
    was_published = post.status == "published"
    post.status, post.deleted_at = "blocked", datetime.now(UTC)
    if was_published:
        await users.bump_counts(s, post.author_id, post_count=-1)
        await post_repo.unlink_hashtags(s, post.id)


async def resolve(s: AsyncSession, admin: User, report_id: uuid.UUID, action: str, ip: str) -> None:
    report = await mod_repo.get(s, report_id)
    if report is None:
        raise not_found("Report")
    if report.status != "open":
        raise conflict("already_resolved", "Someone already resolved this report")
    removed_post = None
    removed_comment = None
    removed = False
    target_user = None
    if report.entity_type == "post":
        post = await post_repo.get(s, report.entity_id)
        if post:
            target_user = post.author_id
            if action == "remove_content":
                await _remove_post(s, post)
                removed_post, removed = post, True
    elif report.entity_type == "comment":
        comment = await comment_repo.get(s, report.entity_id)
        if comment:
            target_user = comment.author_id
            if action == "remove_content":
                comment.deleted_at = datetime.now(UTC)
                if comment.parent_id and not comment.held:
                    await comment_repo.bump_replies(s, comment.parent_id, -1)
                removed_comment, removed = comment, True
    elif report.entity_type == "story":
        story = await story_repo.get(s, report.entity_id)
        if story:
            target_user = story.author_id
            if action == "remove_content":
                await story_repo.remove(s, story.id)
                removed = True
    elif report.entity_type == "community":
        community_post = await get_post_for_report(s, report.entity_id)
        if community_post:
            target_user = community_post.author_id
            if action == "remove_content":
                community_post.deleted_at = datetime.now(UTC)
                removed = True
    elif report.entity_type == "user":
        target_user = report.entity_id
    elif report.entity_type == "message":
        target_user = await chat_repo.sender_of(s, report.entity_id)
    if action == "remove_content" and not removed:
        raise bad_request("nothing_to_remove", "There is no content to remove for this report")
    if action == "suspend_user":
        user = await users.by_id(s, target_user) if target_user else None
        if user is None:
            raise bad_request("no_target", "This account no longer exists")
        if user.role == "superadmin" or (user.role == "admin" and admin.role != "superadmin"):
            raise forbidden("You cannot suspend this staff member")
        user.status = "suspended"
    now = datetime.now(UTC)
    report.resolved_by, report.resolved_at = admin.id, now
    report.status = "dismissed" if action == "dismiss" else "actioned"
    if removed:  # the content is gone, so other reports about it have nothing left to review
        await s.execute(
            update(Report).where(Report.entity_id == report.entity_id, Report.status == "open", Report.id != report.id)
            .values(status="actioned", resolved_by=admin.id, resolved_at=now)
        )
    await users.audit(s, admin.id, f"admin.report.{action}", str(report.id), ip)
    await s.commit()
    if removed_comment and not removed_comment.held:
        await counter_incr(removed_comment.post_id, "comment_count", -1)
    if removed_post:
        await posts.invalidate(removed_post.id)
        await emit("post.deleted", post_id=removed_post.id, author_id=removed_post.author_id)
